/***************************************************************************
  Kombinierter Sensor-Sketch für:
   - BME280 (Temperatur, Luftfeuchtigkeit, Luftdruck)
   - CCS811 (eCO2, TVOC)
   - MQ7 (CO-Konzentration in ppm)

  Alle Sensordaten werden im Serial Monitor ausgegeben und optional auf dem OLED.
  
  Verkabelung:
   OLED (primärer I²C-Bus): SDA_OLED = 17, SCL_OLED = 18, RST_OLED = 21.
   Sensor-I²C (Wire2): SDA = 41, SCL = 42 (für BME280 und CCS811).
   MQ7: Analog (AO) an A0; Heizer-PWM an Pin 5.
  
  Bibliotheken: 
   - HT_SSD1306Wire, images.h
   - Adafruit_BME280, Adafruit_CCS811
   - MQUnifiedsensor
***************************************************************************/

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_CCS811.h>

//#include "HT_SSD1306Wire.h"
#include "images.h"
#include <MQUnifiedsensor.h>
#include "esp32-hal-ledc.h"  // Für ledcSetup, ledcAttachPin, etc.
#include <Arduino.h>
extern "C" {
  #include "driver/ledc.h"
}

// Falls I2C_ONE nicht definiert ist:
#ifndef I2C_ONE
  #define I2C_ONE 0
#endif

// OLED-Pin-Definitionen (verwenden wir hier explizit)
#define SDA_OLED 17
#define SCL_OLED 18
#define RST_OLED 21
#define OLED_UPDATE_INTERVAL 500

TwoWire Wire2(1);

// Erstelle das OLED-Display-Objekt (primärer I²C-Bus)
//static SSD1306Wire display(0x3C, 500000, SDA_OLED, SCL_OLED, GEOMETRY_128_64, RST_OLED);

// Erstelle den zweiten I²C-Bus für Sensoren (BME280 und CCS811)
TwoWire sensorI2CBus = TwoWire(1);

// BME280-Objekt (Wunschadresse: 0x76, alternative: 0x77)
Adafruit_BME280 bme;

// CCS811-Objekt (Wunschadresse: 0x5A, alternative: 0x5B)
Adafruit_CCS811 ccs;

// MQ7-Einstellungen: Wir verwenden die MQUnifiedsensor-Bibliothek
// Parameter anpassen: Für den ESP32 verwenden wir hier (bitte anpassen, falls nötig)
#define Board "ESP-32"
#define MQ7_pin (6)    // analog pin für MQ7 (auf ESP32 entspricht A0 meist GPIO36 oder ein anderer ADC-Pin; passe an, falls nötig)
#define placa "ESP32"
#define Voltage_Resolution 5   // Versorgungsspannung
#define ADC_Bit_Resolution 10    // ESP32 ADC Auflösung
#define RatioMQ7CleanAir 27.5    // typischer Wert: RS/R0 = 27.5
#define PWMPin 6               // PWM-Pin für MQ7-Heizung (wird über LEDC gesteuert)

MQUnifiedsensor MQ7(placa, Voltage_Resolution, ADC_Bit_Resolution, MQ7_pin, "MQ-7");

unsigned long oldTime = 0;
unsigned long delayTime;


////// MessdatenPlatzhalter ///// 
  float bmeTemp = 0.0f;
  float bmeHum  = 0.0f;
  float bmePres = 0.0f;

   float ccsECO2 = 0.0f;
   float ccsTVOC = 0.0f;

   float mq7Value = 0.0f;

///// LORA SETUP//// 
#include "LoRaWan_APP.h"

/* OTAA para*/
uint8_t devEui[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };    //hier Ihre devEUI einfügen
uint8_t appEui[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };    //hier Ihre appEUI einfügen
uint8_t appKey[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };  //hier Ihre appKey einfügen

/* ABP para*/
uint8_t nwkSKey[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,0x00 };
uint8_t appSKey[] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,0x00 };
uint32_t devAddr =  ( uint32_t )0x007e6ae1;

/*LoraWan channelsmask, default channels 0-7*/ 
uint16_t userChannelsMask[6]={ 0x00FF,0x0000,0x0000,0x0000,0x0000,0x0000 };

/*LoraWan region, select in arduino IDE tools*/
LoRaMacRegion_t loraWanRegion = ACTIVE_REGION;

/*LoraWan Class, Class A and Class C are supported*/
DeviceClass_t  loraWanClass = CLASS_A;

/*the application data transmission duty cycle.  value in [ms].*/
uint32_t appTxDutyCycle = 15000;

/*OTAA or ABP*/
bool overTheAirActivation = true;

/*ADR enable*/
bool loraWanAdr = true;

/* Indicates if the node is sending confirmed or unconfirmed messages */
bool isTxConfirmed = true;

/* Application port */
uint8_t appPort = 2;
/*!
* Number of trials to transmit the frame, if the LoRaMAC layer did not
* receive an acknowledgment. The MAC performs a datarate adaptation,
* according to the LoRaWAN Specification V1.0.2, chapter 18.4, according
* to the following table:
*
* Transmission nb | Data Rate
* ----------------|-----------
* 1 (first)       | DR
* 2               | DR
* 3               | max(DR-1,0)
* 4               | max(DR-1,0)
* 5               | max(DR-2,0)
* 6               | max(DR-2,0)
* 7               | max(DR-3,0)
* 8               | max(DR-3,0)
*
* Note, that if NbTrials is set to 1 or 2, the MAC will not decrease
* the datarate, in case the LoRaMAC layer did not receive an acknowledgment
*/
uint8_t confirmedNbTrials = 4;

static void prepareTxFrame( uint8_t port )
{
  /*appData size is LORAWAN_APP_DATA_MAX_SIZE which is defined in "commissioning.h".
  *appDataSize max value is LORAWAN_APP_DATA_MAX_SIZE.
  *if enabled AT, don't modify LORAWAN_APP_DATA_MAX_SIZE, it may cause system hanging or failure.
  *if disabled AT, LORAWAN_APP_DATA_MAX_SIZE can be modified, the max value is reference to lorawan region and SF.
  *for example, if use REGION_CN470, 
  *the max value for different DR can be found in MaxPayloadOfDatarateCN470 refer to DataratesCN470 and BandwidthsCN470 in "RegionCN470.h".
  */
  union {
    float f[6];
    uint8_t b[24];
  } float2bytes;

    float2bytes.f[0] = bmeTemp;
    float2bytes.f[1] = bmeHum;
    float2bytes.f[2] = bmePres;
    float2bytes.f[3] = ccsECO2;
    float2bytes.f[4] = ccsTVOC;
    float2bytes.f[5] = mq7Value;

    appDataSize = 24;
    for (int i = 0; i < 24; i++) {
    appData[i] = float2bytes.b[i];
  }
}

//////////////////////
// Setup            //
//////////////////////
void setup() {
  Serial.begin(115200);
  Mcu.begin(HELTEC_BOARD,SLOW_CLK_TPYE);
  pinMode(PWMPin, OUTPUT);
  delay(100);


  Serial.println("Combined Sensor Setup gestartet...");

  // Initialisiere den primären I²C-Bus für das OLED-Display
  Wire.begin(SDA_OLED, SCL_OLED);
  
  /*
  // OLED initialisieren
  display.init();
  display.clear();
  display.setContrast(255);
  display.drawString(0, 0, "Sensors test...");
  display.display();
  Serial.println("OLED initialisiert");
  */

  // Initialisiere den zweiten I²C-Bus für Sensoren (BME280, CCS811)
  sensorI2CBus.begin(41, 42, 400000);
  Serial.println("Sensor-I²C-Bus initialisiert");

  // Flexible Initialisierung BME280: Versuche zuerst Adresse 0x76, dann alternativ 0x77
  bool status = bme.begin(0x76, &sensorI2CBus);
  if (!status) {
    Serial.println("BME280 nicht gefunden an Adresse 0x76, versuche 0x77...");
    status = bme.begin(0x77, &sensorI2CBus);
    if (status) {
      Serial.println("BME280 gefunden an Adresse 0x77");
    } else {
      Serial.println("BME280-Initialisierung fehlgeschlagen! Check wiring.");
      while (1) delay(10);
    }
  } else {
    Serial.println("BME280 gefunden an Adresse 0x76");
  }

  // Flexible Initialisierung CCS811: Versuche zuerst Adresse 0x5A, dann alternativ 0x5B
  status = ccs.begin(0x5A, &sensorI2CBus);
  if (!status) {
    Serial.println("CCS811 nicht gefunden an Adresse 0x5A, versuche 0x5B...");
    status = ccs.begin(0x5B, &sensorI2CBus);
    if (status) {
      Serial.println("CCS811 gefunden an Adresse 0x5B");
    } else {
      Serial.println("CCS811-Initialisierung fehlgeschlagen! Check wiring.");
      while (1) delay(10);
    }
  } else {
    Serial.println("CCS811 gefunden an Adresse 0x5A");
  }
  while(!ccs.available()){
    Serial.println("Warte auf CCS811...");
    delay(100);
  }
  Serial.println("CCS811 initialisiert");

  // MQ7 initialisieren und kalibrieren
  MQ7.setRegressionMethod(1); // _PPM = a * ratio^b
  MQ7.setA(99.042);
  MQ7.setB(-1.518);
  MQ7.init();
  MQ7.setRL(10); 
  Serial.print("MQ7 Kalibrierung, bitte warten");
  float calcR0 = 0;
  for (int i = 0; i < 10; i++) {
    MQ7.update();
    calcR0 += MQ7.calibrate(RatioMQ7CleanAir);
    Serial.print(".");
    delay(1000);
  }
  MQ7.setR0(calcR0 / 10);
  Serial.println(" done!");
  if (isinf(calcR0)) {
    Serial.println("Warnung: R0 ist unendlich! Überprüfe Verkabelung.");
    while (1) delay(10);
  }
  if (calcR0 == 0) {
    Serial.println("Warnung: R0 ist 0! Überprüfe Verkabelung.");
    while (1) delay(10);
  }
  MQ7.serialDebug(true);
  Serial.println("MQ7 kalibriert");

  delayTime = 200;
  Serial.println("Setup abgeschlossen.");
}

//////////////////////
// Loop             //
//////////////////////
void loop() {

  switch( deviceState )
  {
    case DEVICE_STATE_INIT:
    {
#if(LORAWAN_DEVEUI_AUTO)
      LoRaWAN.generateDeveuiByChipID();
#endif
      LoRaWAN.init(loraWanClass,loraWanRegion);
      //both set join DR and DR when ADR off 
      LoRaWAN.setDefaultDR(3);
      break;
    }
    case DEVICE_STATE_JOIN:
    {
      LoRaWAN.join();
      break;
    }
    case DEVICE_STATE_SEND:
    {
       // Lese BME280-Daten
  bmeTemp = bme.readTemperature();
  bmeHum  = bme.readHumidity();
  bmePres = (bme.readPressure() + 4312) / 100.0F;
  
  // Aktualisiere CCS811-Daten: Zuerst Sensordaten lesen
  if (ccs.available()) {
    if (!ccs.readData()) { 
      ccsECO2 = (float)ccs.geteCO2();
      ccsTVOC = (float)ccs.getTVOC();
    }
  }
  
      // MQ7: Schalte den Heizer kurz auf 100%, lies den Sensor und setze dann auf niedrigen Wert
      analogWrite(PWMPin, 255);  // Setze Heizer auf 100% Duty Cycle
      delay(100);                // Kurze Wartezeit, um den Heizer anzuschalten
      MQ7.update();
      mq7Value = MQ7.readSensor();
      analogWrite(PWMPin, 20);   // Reduziere die Heizleistung, um Überhitzung zu vermeiden
      
      // Ausgabe im Serial Monitor:
      Serial.println("==== Sensordaten ====");
      Serial.print("BME280 - Temp: "); Serial.print(bmeTemp); Serial.print(" C, ");
      Serial.print("Hum: "); Serial.print(bmeHum); Serial.print(" %, ");
      Serial.print("Pres: "); Serial.print(bmePres); Serial.println(" hPa");
      
      Serial.print("CCS811 - eCO2: "); Serial.print(ccsECO2); Serial.print(" ppm, ");
      Serial.print("TVOC: "); Serial.print(ccsTVOC); Serial.println(" ppb");
      
      Serial.print("MQ7 - CO: "); Serial.print(mq7Value); Serial.println(" ppm");
      Serial.println();
      prepareTxFrame( appPort );
      LoRaWAN.send();
      deviceState = DEVICE_STATE_CYCLE;
      break;
    }
    case DEVICE_STATE_CYCLE:
    {
      // Schedule next packet transmission
      
 
  
      txDutyCycleTime = appTxDutyCycle + randr( -APP_TX_DUTYCYCLE_RND, APP_TX_DUTYCYCLE_RND );
      LoRaWAN.cycle(txDutyCycleTime);
      deviceState = DEVICE_STATE_SLEEP;
      break;
    }
    case DEVICE_STATE_SLEEP:
    {
      LoRaWAN.sleep(loraWanClass);
      break;
    }
    default:
    {
      deviceState = DEVICE_STATE_INIT;
      break;
    }
  }

  // OLED-Ausgabe:
  /*
  display.clear();
  display.setFont(ArialMT_Plain_10);
  display.setTextAlignment(TEXT_ALIGN_LEFT);
  display.drawString(0, 0, "BME280:");
  display.drawString(0, 10, "T:" + String(bmeTemp, 1) + " C");
  display.drawString(0, 20, "H:" + String(bmeHum, 1) + " %");
  display.drawString(0, 30, "P:" + String(bmePres, 1) + " hPa");
  display.drawString(0, 40, "CCS811:");
  display.drawString(0, 50, "eCO2:" + String(ccsECO2) + " ppm");
  display.drawString(0, 60, "MQ7:" + String(mq7Value, 1) + " ppm");
  display.display();
  */
  
}