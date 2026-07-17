#include <Arduino.h>
#include "soc/gpio_reg.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "driver/uart.h"

// ==================== PIN & CONFIG ====================
#define ECG_PIN 36
#define LO_PLUS 16
#define LO_MINUS 17

// UART2
#define UART2_TX_PIN 4
#define UART2_RX_PIN 5
#define UART_NUM UART_NUM_2
#define BAUD_RATE 115200

// ==================== STRUCT & ENUM ====================
enum HeartStatus
{
  NORMAL = 0,
  BRADYCARDIA = 1,
  TACHYCARDIA = 2,
  LEADS_OFF = 3
};

struct EcgSample
{
  int value;
  unsigned long timestamp;
};

struct Package
{
  int rawValue;
  int filteredValue;
  float bpm;
  HeartStatus status;
};

// Queues
QueueHandle_t rawEcgQueue;
QueueHandle_t processedQueue;

// ==================== HELPER ====================
static inline void gpio_input_enable(uint32_t pin)
{
  WRITE_PERI_REG(GPIO_ENABLE_W1TC_REG, (1ULL << pin)); // Disable output
}

static inline uint32_t gpio_read_level(uint32_t pin)
{
  return (READ_PERI_REG(GPIO_IN_REG) & (1ULL << pin)) ? 1 : 0;
}

// ADC
static void adc_init(void)
{
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(ADC1_CHANNEL_0, ADC_ATTEN_DB_12);
}

static int adc_read(void)
{
  return adc1_get_raw(ADC1_CHANNEL_0);
}

// UART2
static void uart2_init(void)
{
  uart_config_t uart_config = {
      .baud_rate = BAUD_RATE,
      .data_bits = UART_DATA_8_BITS,
      .parity = UART_PARITY_DISABLE,
      .stop_bits = UART_STOP_BITS_1,
      .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
      .rx_flow_ctrl_thresh = 122,
      .source_clk = UART_SCLK_APB,
  };

  uart_param_config(UART_NUM, &uart_config);
  uart_set_pin(UART_NUM, UART2_TX_PIN, UART2_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
  uart_driver_install(UART_NUM, 1024, 0, 0, NULL, 0);
}

static void uart2_print(const char *str)
{
  uart_write_bytes(UART_NUM, str, strlen(str));
}

static unsigned long get_millis(void)
{
  return (unsigned long)(esp_timer_get_time() / 1000ULL);
}

// ==================== TASK ADC ====================
void TaskADC(void *pvParameters)
{
  EcgSample sample;
  for (;;)
  {
    sample.timestamp = get_millis();

    if ((gpio_read_level(LO_PLUS) == 0) && (gpio_read_level(LO_MINUS) == 0))
    {
      sample.value = adc_read();
    }
    else
    {
      sample.value = -1;
    }

    xQueueSend(rawEcgQueue, &sample, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

#define WINDOW_SIZE 6

void TaskProcessECG(void *pvParameters)
{
  EcgSample receivedSample;
  float lowPass = 0.0f;
  float highPass = 0.0f;
  unsigned long lastPeakTime = 0;
  unsigned long currentTime = 0;
  int lastValue = 0;
  int filteredValue = 0;
  float bpm = 0.0f;
  int receivedRaw = 0;
  HeartStatus currentStatus = NORMAL;

  static float prev_highPass = 0.0f;
  static float moving_average_buffer[WINDOW_SIZE] = {0};
  static int moving_average_index = 0;
  static float moving_sum = 0.0f;

  float derivative = 0.0f;
  float squared = 0.0f;

  float signalLevel = 57000.0f;
  float noiseLevel = 750.0f;
  float threshold = 15000.0f;
  int localMax = 0;
  static bool peakStateRecorded = false;

  for (;;)
  {
    if (xQueueReceive(rawEcgQueue, &receivedSample, portMAX_DELAY))
    {
      currentTime = receivedSample.timestamp;
      receivedRaw = receivedSample.value;

      if (receivedRaw != -1)
      {
        lowPass = lowPass * 0.92f + (float)receivedRaw * 0.08f;
        highPass = (float)receivedRaw - lowPass;

        derivative = highPass - prev_highPass;
        prev_highPass = highPass;

        squared = (derivative * derivative) * 0.1f;

        moving_sum -= moving_average_buffer[moving_average_index];
        moving_average_buffer[moving_average_index] = squared;
        moving_sum += squared;
        moving_average_index = (moving_average_index + 1) % WINDOW_SIZE;
        filteredValue = (int)(moving_sum / (float)WINDOW_SIZE);

        if (filteredValue > (int)threshold)
        {
          if (filteredValue < lastValue && !peakStateRecorded)
          {
            localMax = lastValue;
            unsigned long timeSinceLastPeak = currentTime - lastPeakTime;
            if (timeSinceLastPeak > 500)
            {
              lastPeakTime = currentTime;
              bpm = 60000.0f / timeSinceLastPeak;
              signalLevel = 0.125f * (float)localMax + 0.875f * signalLevel;
              peakStateRecorded = true;
            }
          }
        }
        else
        {
          if (peakStateRecorded)
          {
            peakStateRecorded = false;
            localMax = 0;
          }
          if (filteredValue < (int)(threshold * 0.5f))
          {
            float temp_noise = 0.125f * (float)filteredValue + 0.875f * noiseLevel;
            noiseLevel = (temp_noise < signalLevel * 0.08f) ? temp_noise : signalLevel * 0.08f;
          }
        }

        threshold = noiseLevel + 0.25f * (signalLevel - noiseLevel);

        if (currentTime - lastPeakTime > 3500)
        {
          bpm = 0.0f;
          currentStatus = BRADYCARDIA;
        }
        else if (bpm > 0.0f && bpm < 60.0f)
        {
          currentStatus = BRADYCARDIA;
        }
        else if (bpm > 100.0f)
        {
          currentStatus = TACHYCARDIA;
        }
        else if (bpm >= 60.0f && bpm <= 100.0f)
        {
          currentStatus = NORMAL;
        }

        lastValue = filteredValue;
      }
      else
      {
        filteredValue = 0;
        if (currentTime - lastPeakTime > 4000)
          bpm = 0.0f;
        currentStatus = LEADS_OFF;

        lowPass = 0.0f;
        prev_highPass = 0.0f;
        moving_average_index = 0;
        moving_sum = 0.0f;
        memset(moving_average_buffer, 0, sizeof(moving_average_buffer));
        peakStateRecorded = false;
        localMax = 0;
        signalLevel = 57000.0f;
        noiseLevel = 750.0f;
        threshold = 15000.0f;
      }

      Package dataToSend = {receivedRaw, filteredValue, bpm, currentStatus};
      xQueueSend(processedQueue, &dataToSend, 0);
    }
  }
}

void TaskSerialPrint(void *pvParameters)
{
  Package receivedData;
  char buf[128];

  for (;;)
  {
    if (xQueueReceive(processedQueue, &receivedData, portMAX_DELAY))
    {
      unsigned long now = get_millis();

      Serial.print(now);
      Serial.print(",");
      Serial.print(receivedData.rawValue);
      Serial.print(",");
      Serial.print(receivedData.filteredValue);
      Serial.print(",");
      Serial.print(receivedData.bpm, 1);
      Serial.print(",");

      switch (receivedData.status)
      {
      case NORMAL:
        Serial.println("NORMAL");
        break;
      case BRADYCARDIA:
        Serial.println("BRADYCARDIA");
        break;
      case TACHYCARDIA:
        Serial.println("TACHYCARDIA");
        break;
      case LEADS_OFF:
        Serial.println("LEADS_OFF");
        break;
      }

      snprintf(buf, sizeof(buf), "%lu,%d,%d,%.1f,%d\r\n",
               now, receivedData.rawValue, receivedData.filteredValue,
               receivedData.bpm, (int)receivedData.status);
      uart2_print(buf);
    }
  }
}

// ==================== SETUP ====================
void setup()
{
  Serial.begin(115200);

  gpio_input_enable(LO_PLUS);
  gpio_input_enable(LO_MINUS);
  gpio_input_enable(ECG_PIN);

  adc_init();
  uart2_init();

  rawEcgQueue = xQueueCreate(50, sizeof(EcgSample));
  processedQueue = xQueueCreate(50, sizeof(Package));

  if (rawEcgQueue != NULL && processedQueue != NULL)
  {
    Serial.println("Timestamp(ms),Raw_Value,Filtered_Value,BPM,Status");

    xTaskCreatePinnedToCore(TaskADC, "ADC", 2048, NULL, 3, NULL, 1);
    xTaskCreatePinnedToCore(TaskProcessECG, "Process", 4096, NULL, 2, NULL, 1);
    xTaskCreatePinnedToCore(TaskSerialPrint, "SerialOut", 3072, NULL, 1, NULL, 1);
  }
  else
  {
    Serial.println("Queue creation failed!");
  }
}

void loop()
{
  vTaskDelay(pdMS_TO_TICKS(1000));
}
