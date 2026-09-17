#include <stdio.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"
#include "esp_log.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"


/* =========================================================
 * TAG
 * ========================================================= */

#define TAG "BOT"


/* =========================================================
 * MOTOR PINS
 * ========================================================= */

#define M1_PIN 18
#define M2_PIN 19
#define M3_PIN 22
#define M4_PIN 21


/* =========================================================
 * ULTRASONIC SENSOR
 * ========================================================= */

#define ULTRASONIC_TRIG 25
#define ULTRASONIC_ECHO 26


/* =========================================================
 * MQ-5 GAS SENSOR
 *
 * GPIO34 = ADC1_CHANNEL_6 on classic ESP32
 * ========================================================= */

#define MQ5_ADC_CHANNEL ADC_CHANNEL_6


/* =========================================================
 * DHT22
 * ========================================================= */

#define DHT22_PIN 27


/* =========================================================
 * DVP CAMERA
 * ========================================================= */

#define CAM_D0     4
#define CAM_D1     5
#define CAM_D2     13
#define CAM_D3     14
#define CAM_D4     16
#define CAM_D5     17
#define CAM_D6     23
#define CAM_D7     32

#define CAM_XCLK   33
#define CAM_PCLK   34
#define CAM_HREF   35
#define CAM_VSYNC  39

#define CAM_SDA    15
#define CAM_SCL    2


/* =========================================================
 * ADC HANDLE
 * ========================================================= */

static adc_oneshot_unit_handle_t adc_handle;


/* =========================================================
 * FUNCTION PROTOTYPES
 * ========================================================= */

/* Motor */
static void motor_init(void);
static void motor_forward(void);
static void motor_backward(void);
static void motor_left(void);
static void motor_right(void);
static void motor_stop(void);

/* Ultrasonic */
static void ultrasonic_init(void);

/* MQ-5 */
static void mq5_init(void);
static int mq5_read(void);

/* DHT22 */
static void dht22_init(void);

/* Camera */
static void camera_gpio_init(void);

/* Task */
static void sensor_task(void *arg);


/* =========================================================
 * MOTOR
 * ========================================================= */

static void motor_init(void)
{
    gpio_config_t config = {
        .pin_bit_mask =
            (1ULL << M1_PIN) |
            (1ULL << M2_PIN) |
            (1ULL << M3_PIN) |
            (1ULL << M4_PIN),

        .mode = GPIO_MODE_OUTPUT,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(gpio_config(&config));

    motor_stop();
}


static void motor_forward(void)
{
    gpio_set_level(M1_PIN, 1);
    gpio_set_level(M2_PIN, 0);

    gpio_set_level(M3_PIN, 1);
    gpio_set_level(M4_PIN, 0);
}


static void motor_backward(void)
{
    gpio_set_level(M1_PIN, 0);
    gpio_set_level(M2_PIN, 1);

    gpio_set_level(M3_PIN, 0);
    gpio_set_level(M4_PIN, 1);
}


static void motor_left(void)
{
    gpio_set_level(M1_PIN, 0);
    gpio_set_level(M2_PIN, 1);

    gpio_set_level(M3_PIN, 1);
    gpio_set_level(M4_PIN, 0);
}


static void motor_right(void)
{
    gpio_set_level(M1_PIN, 1);
    gpio_set_level(M2_PIN, 0);

    gpio_set_level(M3_PIN, 0);
    gpio_set_level(M4_PIN, 1);
}


static void motor_stop(void)
{
    gpio_set_level(M1_PIN, 0);
    gpio_set_level(M2_PIN, 0);

    gpio_set_level(M3_PIN, 0);
    gpio_set_level(M4_PIN, 0);
}


/* =========================================================
 * ULTRASONIC SENSOR
 * ========================================================= */

static void ultrasonic_init(void)
{
    gpio_config_t trig_config = {
        .pin_bit_mask = (1ULL << ULTRASONIC_TRIG),

        .mode = GPIO_MODE_OUTPUT,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(gpio_config(&trig_config));


    gpio_config_t echo_config = {
        .pin_bit_mask = (1ULL << ULTRASONIC_ECHO),

        .mode = GPIO_MODE_INPUT,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(gpio_config(&echo_config));

    gpio_set_level(ULTRASONIC_TRIG, 0);
}


/* =========================================================
 * MQ-5 ADC
 * ========================================================= */

static void mq5_init(void)
{
    adc_oneshot_unit_init_cfg_t adc_config = {
        .unit_id = ADC_UNIT_1,
        .ulp_mode = ADC_ULP_MODE_DISABLE
    };

    ESP_ERROR_CHECK(
        adc_oneshot_new_unit(
            &adc_config,
            &adc_handle
        )
    );


    adc_oneshot_chan_cfg_t channel_config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12
    };

    ESP_ERROR_CHECK(
        adc_oneshot_config_channel(
            adc_handle,
            MQ5_ADC_CHANNEL,
            &channel_config
        )
    );
}


static int mq5_read(void)
{
    int raw_value = 0;

    esp_err_t error = adc_oneshot_read(
        adc_handle,
        MQ5_ADC_CHANNEL,
        &raw_value
    );

    if (error != ESP_OK) {

        ESP_LOGE(
            TAG,
            "MQ-5 ADC read failed: %s",
            esp_err_to_name(error)
        );

        return -1;
    }

    return raw_value;
}


/* =========================================================
 * DHT22
 * ========================================================= */

static void dht22_init(void)
{
    gpio_config_t config = {
        .pin_bit_mask = (1ULL << DHT22_PIN),

        .mode = GPIO_MODE_INPUT_OUTPUT_OD,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_ENABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(gpio_config(&config));

    gpio_set_level(DHT22_PIN, 1);
}


/* =========================================================
 * DVP CAMERA GPIO
 * ========================================================= */

static void camera_gpio_init(void)
{
    /*
     * Camera data bus D0-D7
     */

    gpio_config_t camera_data_config = {
        .pin_bit_mask =
            (1ULL << CAM_D0) |
            (1ULL << CAM_D1) |
            (1ULL << CAM_D2) |
            (1ULL << CAM_D3) |
            (1ULL << CAM_D4) |
            (1ULL << CAM_D5) |
            (1ULL << CAM_D6) |
            (1ULL << CAM_D7),

        .mode = GPIO_MODE_INPUT,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(
        gpio_config(&camera_data_config)
    );


    /*
     * Camera synchronization signals
     */

    gpio_config_t camera_sync_config = {
        .pin_bit_mask =
            (1ULL << CAM_PCLK) |
            (1ULL << CAM_HREF) |
            (1ULL << CAM_VSYNC),

        .mode = GPIO_MODE_INPUT,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(
        gpio_config(&camera_sync_config)
    );


    /*
     * Camera clock output
     *
     * This only configures the GPIO.
     * A real XCLK signal still needs to be generated.
     */

    gpio_config_t camera_clock_config = {
        .pin_bit_mask = (1ULL << CAM_XCLK),

        .mode = GPIO_MODE_OUTPUT,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(
        gpio_config(&camera_clock_config)
    );

    gpio_set_level(CAM_XCLK, 0);


    /*
     * Camera SCCB/I2C pins
     */

    gpio_config_t camera_control_config = {
        .pin_bit_mask =
            (1ULL << CAM_SDA) |
            (1ULL << CAM_SCL),

        .mode = GPIO_MODE_INPUT_OUTPUT_OD,

        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_ENABLE,

        .intr_type = GPIO_INTR_DISABLE
    };

    ESP_ERROR_CHECK(
        gpio_config(&camera_control_config)
    );

    gpio_set_level(CAM_SDA, 1);
    gpio_set_level(CAM_SCL, 1);
}


/* =========================================================
 * SENSOR TASK
 * ========================================================= */

static void sensor_task(void *arg)
{
    (void)arg;

    while (1) {

        int gas_value = mq5_read();

        if (gas_value >= 0) {

            ESP_LOGI(
                TAG,
                "MQ-5 RAW: %d",
                gas_value
            );
        }


        /*
         * Ultrasonic sensor:
         *
         * Trigger pulse and echo timing
         * will be implemented here.
         */


        /*
         * DHT22:
         *
         * Temperature and humidity
         * reading will be implemented here.
         */


        /*
         * Camera:
         *
         * DVP frame capture will be
         * implemented here.
         */


        vTaskDelay(
            pdMS_TO_TICKS(1000)
        );
    }
}


/* =========================================================
 * MAIN
 * ========================================================= */

void app_main(void)
{
    ESP_LOGI(
        TAG,
        "Initializing SIH BOT..."
    );


    /* Initialize motors */

    motor_init();


    /* Initialize ultrasonic sensor */

    ultrasonic_init();


    /* Initialize MQ-5 */

    mq5_init();


    /* Initialize DHT22 */

    dht22_init();


    /* Initialize camera GPIO */

    camera_gpio_init();


    /* Make sure motors are stopped */

    motor_stop();


    /* Start sensor task */

    BaseType_t task_result = xTaskCreate(
        sensor_task,
        "sensor_task",
        4096,
        NULL,
        5,
        NULL
    );

    if (task_result != pdPASS) {

        ESP_LOGE(
            TAG,
            "Failed to create sensor task"
        );

        return;
    }


    ESP_LOGI(
        TAG,
        "SIH BOT STARTED"
    );
}
