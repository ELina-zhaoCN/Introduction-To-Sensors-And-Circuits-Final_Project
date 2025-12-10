# Fruit Slicer Game Documentation

---

## Game Name
**Fruit Slicer**

---

## Game Concept
Similar to the "Fruit Ninja" game, fruit fly in straight lines from four directions (up, down, left, right) of the screen. Players need to perform corresponding actions based on the direction the fruit are coming from to "slice" them.

---

## Hardware Configuration
Development Board: Xiao ESP32C3  
Display: SSD1306 OLED  
Accelerometer: ADXL345  
LED: NeoPixels  
Rotary Encoder: Rotary Encoder  
Switch Button: SW_SPST  
Battery: Battery cell 3.7V  
Buzzer: Buzzer 12085

---

## Wiring

### SSD1306 OLED:
VCC → Xiao ESP32C3(3.3V)  
GND → Xiao ESP32C3(GND)  
SCL → Xiao ESP32C3(D5)  
SDA → Xiao ESP32C3(D4)

### ADXL345:
VCC → Xiao ESP32C3(3.3V)  
GND → Xiao ESP32C3(GND)  
SCL → Xiao ESP32C3(D5)  
SDA → Xiao ESP32C3(D4)

### NeoPixels:
VDD → ESP32C3(5V)  
Din → ESP32C3(D10)  
GND → ESP32C3(GND)

### Rotary Encoder:
CLK → ESP32C3(D1)  
GND → ESP32C3(GND)  
DT → ESP32C3(D2)  
VCC → ESP32C3(3.3V)  
SW → ESP32C3(D3)

### Buzzer 12085:
Signal → ESP32C3(D6)  
Power → 3.3V

### Switch Button:
Signal → ESP32C3(D0)  
GND → ESP32C3(GND)

---

## Software Environment
CircuitPython 10.0.3

### Installed Libraries:
```
/
Type    Size    Path    Modified
📁  0 B  adafruit_adxl34x  12/5/2025, 2:49:54 PM
📁  0 B  adafruit_register  12/5/2025, 2:45:34 PM
📁  0 B  lib    12/31/1999, 4:00:02 PM
📁  0 B  sd     12/31/1999, 4:00:02 PM
📄  159 B    boot_out.txt    12/31/1999, 4:00:04 PM
📄  44 B calibration.json   11/10/2025, 2:28:20 PM
📄  550 B    code.py    11/30/2025, 1:47:50 PM
⬇️  1.3 kB   neopixel.mpy   11/14/2025, 5:14:38 AM
⬇️  409 B    rotaryio.mpy   11/14/2025, 5:14:36 AM
📄  119 B    Settings.toml  12/5/2025, 6:30:38 AM

Disk usage: 79.9 kB out of 1.2 MB

/lib/
Type    Size    Path    Modified
📁      ..
📁  0 B  adafruit_bus_device    11/3/2025, 5:17:56 PM
📁  0 B  adafruit_display_shapes    11/30/2025, 7:43:48 PM
📁  0 B  adafruit_display_text 11/3/2025, 6:16:56 PM
⬇️  3.8 kB   adafruit_adxl34x.mpy 11/14/2025, 5:14:36 AM
⬇️  2.0 kB   adafruit_debouncer.mpy   11/14/2025, 5:14:34 AM
⬇️  1.2 kB   adafruit_displayio_ssd1306.mpy 11/14/2025, 5:14:36 AM
⬇️  5.3 kB   adafruit_framebuf.mpy    11/14/2025, 5:14:34 AM
⬇️  2.8 kB   adafruit_ssd1306.mpy 11/14/2025, 5:14:36 AM
⬇️  694 B    adafruit_ticks.mpy   11/14/2025, 5:14:34 AM
```

---
## Function Module and Library Correspondence Overview
Hardware Function	Library/Module Directly Called in Code	Dependent Underlying Library Files (From Your List)	Brief Description of Function Implementation Logic
I2C Communication Bus	busio.I2C	(CircuitPython built-in)	busio.I2C → Operating system low-level driver
Accelerometer (ADXL345)	lib.adafruit_adxl34x	1. /lib/adafruit_adxl34x.mpy
2. /adafruit_adxl34x/
3. Transitive Dependencies: adafruit_bus_device, adafruit_register	Game Code → adafruit_adxl34x.mpy → Read/write registers via I2C (busio) → Obtain XYZ acceleration values
NeoPixel LED	neopixel.NeoPixel	/neopixel.mpy	Game Code → neopixel.mpy → Control GPIO timing sequence → Drive WS2812 LED

## Game Instructions

### Level Design

**Easy Mode (4 Levels):**
- Level 1: Slow speed, 12 fruit, 60 seconds
- Level 2: Medium speed, 15 fruit, 55 seconds
- Level 3: Medium speed, 20 fruit, 50 seconds
- Level 4: Fast speed, 25 fruit, 45 seconds

**Medium Mode (3 Levels):**
- Level 1: Medium speed, 20 fruit, 45 seconds
- Level 2: Fast speed, 25 fruit, 40 seconds
- Level 3: Very fast speed, 30 fruit, 35 seconds

**Hard Mode (3 Levels):**
- Level 1: Fast speed, 25 fruit, 30 seconds
- Level 2: Very fast speed, 30 fruit, 25 seconds
- Level 3: Ultra speed, 35 fruit, 20 seconds

### Game Start
Game Start → Directly select level combination → Start game

Adjusted to select difficulty: Easy, Medium, Hard, defaulting to the first level of each difficulty.

Level Configuration:
```
"E1:EZ 12A 60S", # Easy Level 1: Slow speed, 12 fruit, 60 seconds
"E2:EZ 15A 55S", # Easy Level 2: Slow speed, 15 fruit, 55 seconds
"E3:EZ 20A 50S", # Easy Level 3: Medium speed, 20 fruit, 50 seconds
"E4:EZ 25A 45S", # Easy Level 4: Fast speed, 25 fruit, 45 seconds
"M1:MD 20A 45S", # Medium Level 1: Medium speed, 20 fruit, 45 seconds
"M2:MD 25A 40S", # Medium Level 2: Fast speed, 25 fruit, 40 seconds
"M3:MD 30A 35S", # Medium Level 3: Very fast speed, 30 fruit, 35 seconds
"H1:HD 25A 30S", # Hard Level 1: Fast speed, 25 fruit, 30 seconds
"H2:HD 30A 25S", # Hard Level 2: Very fast speed, 30 fruit, 25 seconds
"H3:HD 35A 20S", # Hard Level 3: Ultra speed, 35 fruit, 20 seconds
```

### Apple Generation

#### Screen Specifications
Resolution: 128×64 pixels

APPLE_SIZE = (8, 8)  # Width 8 pixels

Coordinate origin: Top-left corner (0,0), Bottom-right corner (127,63)

Screen center (63,35)

#### Generation Positions (Four Sides)
1. Top edge: Y=0, X=63
2. Bottom edge: Y=63, X=63
3. Left edge: X=0, Y=31
4. Right edge: X=127, Y=31

#### Generation Rules
Movement direction: Straight line

Each apple randomly selects one of the four edges and moves toward the screen center.

The **initial position** of the apple is the coordinate of the generation point.

The **target position** of the apple is the screen center area.

Apple generation speed is evenly distributed within each level.

Interval = Total time ÷ Total number of fruit

First apple generates at 0 seconds.

Second apple generates after interval seconds.

Third apple generates after 2×interval seconds.

And so on...

### Slicing Fruit

#### Valid Cutting Zone
**Invalid zone**: X∈[45,81], Y∈[27,45] (Center protection zone)

**Valid zone**: All other areas of the screen (within 128×64 pixels)

#### Cutting Conditions (All must be met):
1. **Position condition**: Apple is in the valid zone (not in the invalid zone)
2. **Time condition**: Player performs correct action within **2 seconds** after apple enters valid zone
3. **Action condition**: Player performs action matching the apple's source direction

### Judgment Process
Apple moves → Enters valid zone → 2-second timer starts → Player action → Check

Behavior: Passes through invalid zone.

Timer continues while in invalid zone.

### Status Bar Area
Font: terminalio.FONT

**Game Difficulty - Game Level** Lvl 1 - Stg 3, **Position** Y=2, X=7

**Sliced fruit:Total fruit** Sliced: 12/30, **Position** Y=2, X=45

**Time countdown** Countdown: 0:21 (format: minutes:seconds), **Position** Y=2, X=85

### Game Over Conditions
Time runs out.

Font: SIMPLE_FONT

Automatically proceeds to the next level upon completing the current level.

Display after game over:
- Game Over # End message, **Position** Y=20, X=50
- Sliced: 12/30 # Score, **Position** Y=31, X=49
- Countdown: 0:21 # Timer, **Position** Y=41, X=44

Game cleared: Displays "Congratulations"

---

## Game Rules

Communication Protocol: I2C

Input: ADXL345, Rotary Encoder
Output: NeoPixels, SSD1306 OLED

### Input Logic

**Rotary Encoder: Rotate Right**
Player needs to rotate knob clockwise (CLK).
Responds 0.2s after right rotation, no operation cooldown.

**Rotary Encoder: Rotate Left**
Player needs to rotate knob counterclockwise (DT).
Responds 0.2s after left rotation, no operation cooldown.

**Rotary Encoder: Press Rotary Encoder Button (SW)**
Start game / Restart game.

**ADXL345: +Y Forward Tilt**
Y-axis positive value increases.
Responds 0.2s after tilt, no operation cooldown.

**ADXL345: -Y Backward Tilt**
Y-axis negative value decreases.
Responds 0.2s after tilt, no operation cooldown.

### Output Logic

**NeoPixels Standby/Menu**
LED slowly breathing blue, indicating device is ready, waiting to start.

**NeoPixels Game In Progress**
LED solid green, indicating game is in progress, player performing well.

**NeoPixels Correct/Success**
Quick blue flash once when player action is correct.

**NeoPixels Error/Failure**
Quick red flash once when player action is incorrect.

**NeoPixels Countdown Warning**
When round time is about to end, LED becomes flashing yellow or orange, creating tension.

**NeoPixels Game Over**
LED slowly breathing blue, indicating game has ended, press Rotary Encoder button to restart game.