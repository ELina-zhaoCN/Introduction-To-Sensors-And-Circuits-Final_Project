import time
import math
import random
import board
import busio
import neopixel
from digitalio import DigitalInOut, Direction, Pull

# ==================== Hardware Initialization ====================

print("=" * 50)
print("Apple Slice Game - Starting...")
print("=" * 50)

# Initialize I2C bus
def init_i2c_bus():
    """Initialize I2C bus"""
    try:
        i2c = busio.I2C(board.D5, board.D4)
        print("✓ I2C bus initialized successfully")
        return i2c
    except Exception as e:
        print(f"✗ I2C initialization failed: {e}")
        return None

I2C_BUS = init_i2c_bus()

# OLED display initialization (using debugged custom driver)
print("\nInitializing OLED display...")
OLED_WIDTH = 128
OLED_HEIGHT = 64

class RawOLEDDisplay:
    """Custom OLED driver (verified to work)"""
    def __init__(self, i2c, width=128, height=64, address=0x3C):
        self.i2c = i2c
        self.width = width
        self.height = height
        self.address = address
        self.buffer = bytearray(width * height // 8)
        self._oled_should_be_off = False
        self._init_display()
    
    def _send_command(self, cmd):
        try:
            while not self.i2c.try_lock():
                pass
            self.i2c.writeto(self.address, bytearray([0x00, cmd]))
            self.i2c.unlock()
        except:
            pass
    
    def _send_data(self, data):
        try:
            while not self.i2c.try_lock():
                pass
            if isinstance(data, int):
                self.i2c.writeto(self.address, bytearray([0x40, data]))
            else:
                chunk_size = 16
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    self.i2c.writeto(self.address, bytearray([0x40]) + chunk)
            self.i2c.unlock()
        except:
            pass
    
    def _init_display(self):
        """Initialize OLED"""
        init_sequence = [
            (0xAE, []), (0xD5, [0x80]), (0xA8, [0x3F]), (0xD3, [0x00]),
            (0x40, []), (0x8D, [0x14]), (0x20, [0x00]), (0xA1, []),
            (0xC8, []), (0xDA, [0x12]), (0x81, [0xCF]), (0xD9, [0xF1]),
            (0xDB, [0x40]), (0xA4, []), (0xA6, []), (0xAF, [])
        ]
        
        for cmd, params in init_sequence:
            self._send_command(cmd)
            for param in params:
                self._send_command(param)
            time.sleep(0.002)
        
        self.fill(0)
        self.show()
    
    def fill(self, color):
        fill_byte = 0xFF if color else 0x00
        for i in range(len(self.buffer)):
            self.buffer[i] = fill_byte
    
    def pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            index = (y // 8) * self.width + x
            bit = y % 8
            if color:
                self.buffer[index] |= (1 << bit)
            else:
                self.buffer[index] &= ~(1 << bit)
    
    def fill_rect(self, x, y, w, h, color):
        for py in range(y, min(y + h, self.height)):
            for px in range(x, min(x + w, self.width)):
                self.pixel(px, py, color)
    
    def rect(self, x, y, w, h, color):
        self.fill_rect(x, y, w, 1, color)
        self.fill_rect(x, y + h - 1, w, 1, color)
        self.fill_rect(x, y, 1, h, color)
        self.fill_rect(x + w - 1, y, 1, h, color)
    
    def show(self):
        try:
            self._send_command(0x21)  # Column address
            self._send_command(0)
            self._send_command(self.width - 1)
            
            self._send_command(0x22)  # Page address
            self._send_command(0)
            self._send_command((self.height // 8) - 1)
            
            while not self.i2c.try_lock():
                pass
            chunk_size = 16
            for i in range(0, len(self.buffer), chunk_size):
                chunk = self.buffer[i:i+chunk_size]
                self.i2c.writeto(self.address, bytearray([0x40]) + chunk)
            self.i2c.unlock()
        except:
            pass

# Create OLED display object
display_ok = False
if I2C_BUS:
    try:
        display = RawOLEDDisplay(I2C_BUS, OLED_WIDTH, OLED_HEIGHT, 0x3C)
        display_ok = True
        print("✓ OLED display initialized successfully")
    except:
        print("✗ OLED initialization failed")
        display = None
        display_ok = False
else:
    print("✗ I2C bus unavailable, OLED disabled")
    display = None
    display_ok = False

# -------------------- Accelerometer Calibration & Filter Class --------------------
class CalibratedAccel:
    """Accelerometer wrapper with static calibration and first-order low-pass filter"""
    def __init__(self, accel):
        self.accel = accel
        # Static calibration: calculate offset from 100 stationary samples
        self.x_offset, self.y_offset, self.z_offset = self.calibrate()
        # Low-pass filter parameters (alpha=0.2, adjustable smooth factor)
        self.alpha = 0.2
        self.filtered_x, self.filtered_y, self.filtered_z = 0.0, 0.0, 0.0

    def calibrate(self, samples=100):
        """Static calibration: calculate average offset from multiple stationary readings"""
        x_sum, y_sum, z_sum = 0.0, 0.0, 0.0
        print("Calibrating accelerometer (keep still)...")
        for _ in range(samples):
            try:
                x, y, z = self.accel.acceleration
                x_sum += x
                y_sum += y
                z_sum += z
                time.sleep(0.01)
            except:
                pass
        # Calculate average offset (x/y ≈ 0, z ≈ 9.81 when stationary)
        x_offset = x_sum / samples if samples > 0 else 0.0
        y_offset = y_sum / samples if samples > 0 else 0.0
        z_offset = (z_sum / samples) - 9.81 if samples > 0 else 0.0
        print(f"✓ Accelerometer calibration done - offsets: x={x_offset:.2f}, y={y_offset:.2f}, z={z_offset:.2f}")
        return x_offset, y_offset, z_offset

    @property
    def acceleration(self):
        """Calibrated and filtered acceleration readings (compatible with original interface)"""
        try:
            # Read raw values
            raw_x, raw_y, raw_z = self.accel.acceleration
            # Step 1: Calibration (remove zero offset)
            cal_x = raw_x - self.x_offset
            cal_y = raw_y - self.y_offset
            cal_z = raw_z - self.z_offset
            # Step 2: First-order low-pass filter (remove high-frequency noise)
            self.filtered_x = self.alpha * cal_x + (1 - self.alpha) * self.filtered_x
            self.filtered_y = self.alpha * cal_y + (1 - self.alpha) * self.filtered_y
            self.filtered_z = self.alpha * cal_z + (1 - self.alpha) * self.filtered_z
            # Step 3: Outlier filtering (limit range to avoid jumps)
            clamp = lambda v: max(min(v, 20.0), -20.0)
            return clamp(self.filtered_x), clamp(self.filtered_y), clamp(self.filtered_z)
        except:
            return 0.0, 0.0, 0.0

# ADXL345 accelerometer initialization
print("\nInitializing ADXL345 accelerometer...")
accelerometer = None
if I2C_BUS:
    try:
        # Import from lib (verified to work)
        import lib.adafruit_adxl34x as adafruit_adxl34x
        raw_accel = adafruit_adxl34x.ADXL345(I2C_BUS)
        accelerometer = CalibratedAccel(raw_accel)
        print("✓ ADXL345 accelerometer initialized successfully")
    except Exception as e:
        print(f"✗ ADXL345 initialization failed: {e}")
        print("Tilt control will be disabled")

if not accelerometer:
    class DummyAccel:
        @property
        def acceleration(self):
            return (0.0, 0.0, 0.0)
    accelerometer = DummyAccel()

# NeoPixel LED initialization
print("\nInitializing NeoPixel LED...")
try:
    pixels = neopixel.NeoPixel(board.D9, 1, brightness=0.3, auto_write=True)
    pixels[0] = (0, 0, 0)
    print("✓ NeoPixel LED initialized successfully")
except Exception as e:
    print(f"✗ NeoPixel initialization failed: {e}")
    # Dummy class for compatibility
    class DummyPixels:
        def __setitem__(self, key, value): pass
        @property
        def brightness(self): return 0.5
        @brightness.setter
        def brightness(self, value): pass
    pixels = DummyPixels()

# -------------------- Debounce Utility Function --------------------
def read_pin_stable(pin, samples=5, delay=0.005):
    """Debounced pin reading function"""
    if not pin:
        return False
    values = []
    for _ in range(samples):
        try:
            values.append(pin.value)
            time.sleep(delay)
        except:
            pass
    if not values:
        return pin.value
    # Return the most frequent stable value
    return max(set(values), key=values.count)

# Rotary encoder initialization (using debugged manual method)
print("\nInitializing rotary encoder...")
ENCODER_AVAILABLE = False

try:
    clk_pin = DigitalInOut(board.D1)
    clk_pin.direction = Direction.INPUT
    clk_pin.pull = Pull.UP
    
    dt_pin = DigitalInOut(board.D2)
    dt_pin.direction = Direction.INPUT
    dt_pin.pull = Pull.UP
    
    class ManualEncoder:
        def __init__(self, clk, dt):
            self.clk = clk
            self.dt = dt
            self._position = 0
            self._last_clk = clk.value if clk else None
            self._last_dt = dt.value if dt else None
        
        @property
        def position(self):
            if not self.clk or not self.dt:
                return self._position
            
            # Debounced pin reading
            clk_val = read_pin_stable(self.clk)
            dt_val = read_pin_stable(self.dt)
            
            # Detect CLK falling edge
            if self._last_clk is not None and self._last_dt is not None:
                if self._last_clk and not clk_val:  # CLK from high to low
                    if dt_val:  # DT is high, clockwise
                        self._position += 1
                    else:  # DT is low, counterclockwise
                        self._position -= 1
            
            self._last_clk = clk_val
            self._last_dt = dt_val
            
            return self._position
        
        @position.setter
        def position(self, value):
            self._position = value
    
    encoder = ManualEncoder(clk_pin, dt_pin)
    ENCODER_AVAILABLE = True
    print("✓ Rotary encoder initialized successfully")
except Exception as e:
    print(f"✗ Rotary encoder initialization failed: {e}")
    class DummyEncoder:
        def __init__(self):
            self._position = 0
        @property
        def position(self):
            return self._position
        @position.setter
        def position(self, value):
            self._position = value
    encoder = DummyEncoder()

# Encoder button initialization
print("\nInitializing encoder button...")
try:
    encoder_button = DigitalInOut(board.D3)
    encoder_button.direction = Direction.INPUT
    encoder_button.pull = Pull.DOWN
    print("✓ Encoder button initialized successfully")
except Exception as e:
    print(f"✗ Encoder button initialization failed: {e}")
    encoder_button = None

# Buzzer initialization (active buzzer, inverted logic)
print("\nInitializing buzzer...")
buzzer_available = False
buzzer_is_active = True
BUZZER_INVERTED_LOGIC = True
try:
    buzzer = DigitalInOut(board.D6)
    buzzer.direction = Direction.OUTPUT
    buzzer.value = True  # Initial state: off (inverted logic)
    buzzer_available = True
    print("✓ Buzzer initialized successfully (active, inverted logic)")
except Exception as e:
    print(f"✗ Buzzer initialization failed: {e}")
    buzzer = None
    buzzer_available = False

# Power switch initialization
print("\nInitializing power switch monitoring...")
power_switch = None
try:
    power_switch = DigitalInOut(board.D0)
    power_switch.direction = Direction.INPUT
    power_switch.pull = Pull.UP
    print("✓ Power switch monitoring initialized successfully")
except Exception as e:
    print(f"✗ Power switch monitoring initialization failed: {e}")
    power_switch = None

print("\n" + "=" * 50)
print("Hardware initialization completed")
print("=" * 50)

# ==================== Simple Font ====================

SIMPLE_FONT = {
    '0': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    '1': [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
    '2': [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
    '3': [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
    '4': [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
    '5': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
    '6': [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
    '7': [[1,1,1],[0,0,1],[0,0,1],[0,0,1],[0,0,1]],
    '8': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
    '9': [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
    'E': [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,1,1]],
    'M': [[1,0,1],[1,1,1],[1,0,1],[1,0,1],[1,0,1]],
    'H': [[1,0,1],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
    'Z': [[1,1,1],[0,0,1],[0,1,0],[1,0,0],[1,1,1]],
    'D': [[1,1,0],[1,0,1],[1,0,1],[1,0,1],[1,1,0]],
    'A': [[0,1,0],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
    'S': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
    'G': [[1,1,1],[1,0,0],[1,0,1],[1,0,1],[1,1,1]],
    'O': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    'V': [[1,0,1],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
    'R': [[1,1,0],[1,0,1],[1,1,0],[1,0,1],[1,0,1]],
    'P': [[1,1,1],[1,0,1],[1,1,1],[1,0,0],[1,0,0]],
    'T': [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[0,1,0]],
    'I': [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[1,1,1]],
    'L': [[1,0,0],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],
    'C': [[1,1,1],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],
    'N': [[1,0,1],[1,1,1],[1,0,1],[1,0,1],[1,0,1]],
    'U': [[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    'W': [[1,0,1],[1,0,1],[1,0,1],[1,1,1],[1,0,1]],
    'Y': [[1,0,1],[1,0,1],[0,1,0],[0,1,0],[0,1,0]],
    'K': [[1,0,1],[1,1,0],[1,0,0],[1,1,0],[1,0,1]],
    'F': [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,0,0]],
    ':': [[0],[0],[1],[0],[1]],
    '/': [[0,0,1],[0,1,0],[0,1,0],[1,0,0],[0,0,0]],
    ' ': [[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0]],
}

def draw_char(display, char, x, y, color=1):
    """Draw single character (5x7 pixels)"""
    if char.upper() in SIMPLE_FONT:
        pattern = SIMPLE_FONT[char.upper()]
        for row_idx, row in enumerate(pattern):
            for col_idx, pixel in enumerate(row):
                if pixel:
                    display.pixel(x + col_idx, y + row_idx, color)

def draw_text(display, text, x, y, color=1, spacing=6):
    """Draw text string"""
    current_x = x
    for char in text:
        if char in SIMPLE_FONT or char.upper() in SIMPLE_FONT:
            draw_char(display, char, current_x, y, color)
            current_x += spacing

# ==================== Game Constants ====================

APPLE_SIZE = (8, 8)
SCREEN_CENTER = (63, 35)
INVALID_REGION = {"x_min": 45, "x_max": 81, "y_min": 27, "y_max": 45}
CUT_TIME_LIMIT = 4.0
RESPONSE_DELAY = 0.2

SPAWN_POSITIONS = {
    "top": (63, 0),
    "bottom": (63, 63),
    "left": (0, 31),
    "right": (127, 31)
}

SPEEDS = {
    "slow": 20,
    "medium": 35,
    "fast": 50,
    "very_fast": 70,
    "ultra": 90
}

LEVELS = [
    {"name": "E1:EZ 10A 60S", "speed": "slow", "apples": 10, "time": 60, "difficulty": "easy"},
    {"name": "E2:EZ 15A 55S", "speed": "slow", "apples": 15, "time": 55, "difficulty": "easy"},
    {"name": "E3:EZ 20A 50S", "speed": "medium", "apples": 20, "time": 50, "difficulty": "easy"},
    {"name": "E4:EZ 25A 45S", "speed": "fast", "apples": 25, "time": 45, "difficulty": "easy"},
    {"name": "M1:MD 20A 45S", "speed": "medium", "apples": 20, "time": 45, "difficulty": "medium"},
    {"name": "M2:MD 25A 40S", "speed": "fast", "apples": 25, "time": 40, "difficulty": "medium"},
    {"name": "M3:MD 30A 35S", "speed": "very_fast", "apples": 30, "time": 35, "difficulty": "medium"},
    {"name": "H1:HD 25A 30S", "speed": "fast", "apples": 25, "time": 30, "difficulty": "hard"},
    {"name": "H2:HD 30A 25S", "speed": "very_fast", "apples": 30, "time": 25, "difficulty": "hard"},
    {"name": "H3:HD 35A 20S", "speed": "ultra", "apples": 35, "time": 20, "difficulty": "hard"},
]

DIFFICULTY_LEVELS = {
    "easy": 0,
    "medium": 4,
    "hard": 7,
}

DIFFICULTY_NAMES = ["EASY", "MEDIUM", "HARD"]

# ==================== Game Classes ====================
class GameState:
    MENU = 0
    PLAYING = 1
    GAME_OVER = 2
    PAUSED = 3

class Apple:
    def __init__(self, spawn_direction, speed, start_time):
        self.spawn_direction = spawn_direction
        self.speed = speed
        self.start_time = start_time
        self.sliced = False
        self.entered_valid_zone = False
        self.valid_zone_entry_time = None
        self.expired = False
        
        self.start_pos = SPAWN_POSITIONS[spawn_direction]
        self.target_pos = SCREEN_CENTER
        
        dx = self.target_pos[0] - self.start_pos[0]
        dy = self.target_pos[1] - self.start_pos[1]
        distance = math.sqrt(dx*dx + dy*dy)
        if distance > 0:
            self.direction = (dx/distance, dy/distance)
        else:
            self.direction = (0, 0)
        
        self.x = float(self.start_pos[0])
        self.y = float(self.start_pos[1])
        
        self.expected_action = self._get_expected_action()
    
    def _get_expected_action(self):
        """Return expected action based on spawn direction"""
        if self.spawn_direction == "top":
            return "forward"
        elif self.spawn_direction == "bottom":
            return "backward"
        elif self.spawn_direction == "left":
            return "rotate_left"
        elif self.spawn_direction == "right":
            return "rotate_right"
        return None
    
    def update(self, current_time):
        """Update apple position"""
        if self.sliced or self.expired:
            return
        
        elapsed = current_time - self.start_time
        distance = self.speed * elapsed
        
        self.x = self.start_pos[0] + self.direction[0] * distance
        self.y = self.start_pos[1] + self.direction[1] * distance
        
        if not self.entered_valid_zone:
            if not self._is_in_invalid_region():
                self.entered_valid_zone = True
                self.valid_zone_entry_time = current_time
        
        if self.entered_valid_zone:
            if current_time - self.valid_zone_entry_time > CUT_TIME_LIMIT:
                self.expired = True
        
        if (self.x < -APPLE_SIZE[0] or self.x > OLED_WIDTH + APPLE_SIZE[0] or
            self.y < -APPLE_SIZE[1] or self.y > OLED_HEIGHT + APPLE_SIZE[1]):
            self.expired = True
    
    def _is_in_invalid_region(self):
        """Check if in invalid region"""
        return (INVALID_REGION["x_min"] <= self.x <= INVALID_REGION["x_max"] and
                INVALID_REGION["y_min"] <= self.y <= INVALID_REGION["y_max"])
    
    def is_in_valid_zone(self):
        """Check if in valid cutting zone"""
        return not self._is_in_invalid_region()
    
    def get_pos(self):
        """Get integer position"""
        return (int(self.x), int(self.y))

class Game:
    def __init__(self):
        self.state = GameState.MENU
        self.current_difficulty_index = 0
        self.current_level_index = 0
        self.current_level = None
        self.apples = []
        self.sliced_count = 0
        self.game_start_time = 0
        self.last_apple_spawn_time = 0
        self.apple_spawn_interval = 0
        self.pause_start_time = 0
        self.total_pause_time = 0
        
        # Input state
        try:
            if ENCODER_AVAILABLE:
                self.last_encoder_position = encoder.position
                encoder.position = 0
                self.last_encoder_position = 0
            else:
                self.last_encoder_position = 0
        except:
            self.last_encoder_position = 0
        
        self._update_level_index_from_difficulty()
        self.last_encoder_action_time = 0
        self.last_accel_y = 0.0
        self.last_accel_action_time = 0
        self.encoder_action_pending = None
        self.accel_action_pending = None
        
        # LED state
        self.led_state = "idle"
        self.led_brightness = 0.1
        self.led_brightness_dir = 1
        self.last_led_update = time.monotonic()
        
        # Button state
        self._button_last_state = False
        self._button_press_start_time = 0
        self._button_action_done = False
        
        # Power switch state - initialize carefully
        try:
            self.last_power_switch_state = power_switch.value if power_switch else False
            print(f"[DEBUG] Initial power switch state: {self.last_power_switch_state}")
        except:
            self.last_power_switch_state = False
    
    def start_level(self, level_index):
        """Start specified level"""
        if level_index >= len(LEVELS):
            return False
        
        self.current_level_index = level_index
        self.current_level = LEVELS[level_index]
        self.apples = []
        self.sliced_count = 0
        self.game_start_time = time.monotonic()
        self.last_apple_spawn_time = self.game_start_time
        self.total_pause_time = 0
        
        total_apples = self.current_level["apples"]
        total_time = self.current_level["time"]
        self.apple_spawn_interval = total_time / total_apples if total_apples > 0 else 999
        
        self.state = GameState.PLAYING
        self.led_state = "playing"
        
        # Play start sound
        self._play_sound("start")
        
        return True
    
    def spawn_apple_at_time(self, spawn_time):
        """Spawn a new apple at specified time"""
        if not self.current_level:
            return
        
        direction = random.choice(list(SPAWN_POSITIONS.keys()))
        speed = SPEEDS[self.current_level["speed"]]
        
        apple = Apple(direction, speed, spawn_time)
        self.apples.append(apple)
    
    def update(self):
        """Update game state"""
        try:
            current_time = time.monotonic()
        except:
            return
        
        # Monitor power switch (safe operation)
        try:
            self._monitor_power_switch(current_time)
        except:
            pass
        
        # Update game state based on current state
        try:
            if self.state == GameState.MENU:
                self._update_menu()
            elif self.state == GameState.PLAYING:
                self._update_playing(current_time)
            elif self.state == GameState.GAME_OVER:
                self._update_game_over()
            elif self.state == GameState.PAUSED:
                self._update_paused()
        except Exception as e:
            pass
        
        # Update LEDs (safe operation)
        try:
            self._update_leds(current_time)
        except:
            pass
        
        # Update inputs (safe operation)
        try:
            self._update_inputs(current_time)
        except:
            pass
    
    def _monitor_power_switch(self, current_time):
        """Monitor power switch state and control OLED"""
        if not power_switch:
            return
        
        try:
            # Debounced power switch reading
            switch_state = read_pin_stable(power_switch)
            
            # Debug output every 2 seconds
            if not hasattr(self, '_last_switch_debug_time'):
                self._last_switch_debug_time = 0
            
            if current_time - self._last_switch_debug_time > 2.0:
                print(f"[DEBUG] Switch state: {switch_state} (last: {self.last_power_switch_state})")
                self._last_switch_debug_time = current_time
            
            # Detect state changes
            if switch_state != self.last_power_switch_state:
                print(f"[POWER] *** STATE CHANGE DETECTED ***")
                print(f"[POWER] Old state: {self.last_power_switch_state}, New state: {switch_state}")
                
                if switch_state:
                    # Switch turned OFF (HIGH)
                    print("[POWER] Switch turned OFF")
                    if display_ok and display:
                        display._oled_should_be_off = True
                        # Send display OFF command
                        try:
                            if hasattr(display, '_send_command'):
                                display._send_command(0xAE)
                                print("[POWER] Display OFF command sent")
                        except Exception as e:
                            print(f"[POWER] Display OFF error: {e}")
                else:
                    # Switch turned ON (LOW)
                    print("[POWER] Switch turned ON - Enabling display")
                    if display_ok and display:
                        display._oled_should_be_off = False
                        # Send display ON command and clear screen
                        try:
                            if hasattr(display, '_send_command'):
                                display._send_command(0xAF)
                                time.sleep(0.05)
                                display.fill(0)
                                display.show()
                                print("[POWER] Display reinitialized and cleared")
                        except Exception as e:
                            print(f"[POWER] Display ON error: {e}")
                
                self.last_power_switch_state = switch_state
        except Exception as e:
            print(f"[POWER] Monitor error: {e}")
    
    def _update_menu(self):
        """Update menu state - select difficulty"""
        current_time = time.monotonic()
        
        # Check encoder for difficulty selection
        if ENCODER_AVAILABLE:
            try:
                encoder_pos = encoder.position
                if encoder_pos != self.last_encoder_position:
                    diff = encoder_pos - self.last_encoder_position
                    if abs(diff) <= 100:
                        if diff > 0:
                            self.current_difficulty_index = (self.current_difficulty_index + 1) % len(DIFFICULTY_NAMES)
                            self._play_sound("menu_move")
                        elif diff < 0:
                            self.current_difficulty_index = (self.current_difficulty_index - 1) % len(DIFFICULTY_NAMES)
                            self._play_sound("menu_move")
                        self._update_level_index_from_difficulty()
                    self.last_encoder_position = encoder_pos
            except:
                pass
        
        # Check button press - long press to start game
        button_current = read_pin_stable(encoder_button)
        
        if button_current and not self._button_last_state:
            self._button_press_start_time = current_time
            self._button_action_done = False
        
        if button_current and self._button_press_start_time > 0:
            hold_time = current_time - self._button_press_start_time
            
            if not self._button_action_done:
                if hold_time >= 1.0:
                    if self.state == GameState.MENU and self.current_level is None:
                        self.start_level(self.current_level_index)
                    self._button_action_done = True
        
        if not button_current and self._button_last_state:
            self._button_action_done = False
            self._button_press_start_time = 0
        
        self._button_last_state = button_current
    
    def _update_level_index_from_difficulty(self):
        """Update level index based on current difficulty index"""
        if self.current_difficulty_index < len(DIFFICULTY_NAMES):
            difficulty_name = DIFFICULTY_NAMES[self.current_difficulty_index].lower()
            if difficulty_name in DIFFICULTY_LEVELS:
                self.current_level_index = DIFFICULTY_LEVELS[difficulty_name]
    
    def _update_playing(self, current_time):
        """Update playing state"""
        # Adjust time for pauses
        adjusted_current_time = current_time - self.total_pause_time
        elapsed = adjusted_current_time - self.game_start_time
        remaining_time = self.current_level["time"] - elapsed
        
        if remaining_time <= 0:
            self.state = GameState.GAME_OVER
            self.led_state = "game_over"
            self._play_sound("game_over")
            return
        
        # Spawn apples
        apples_to_spawn = int(elapsed / self.apple_spawn_interval) + 1
        apples_to_spawn = min(apples_to_spawn, self.current_level["apples"])
        
        while len(self.apples) < apples_to_spawn:
            spawn_time = self.game_start_time + len(self.apples) * self.apple_spawn_interval
            self.spawn_apple_at_time(spawn_time)
        
        # Update all apples
        for apple in self.apples:
            apple.update(adjusted_current_time)
        
        # Check warning state
        if remaining_time <= 10:
            self.led_state = "warning"
    
    def _update_game_over(self):
        """Update game over state"""
        current_time = time.monotonic()
        
        button_current = read_pin_stable(encoder_button)
        
        if not hasattr(self, '_game_over_button_last_state'):
            self._game_over_button_last_state = False
        if not hasattr(self, '_game_over_button_press_time'):
            self._game_over_button_press_time = 0
        
        if button_current and not self._game_over_button_last_state:
            self._game_over_button_press_time = current_time
        
        if button_current and self._game_over_button_press_time > 0:
            if current_time - self._game_over_button_press_time > 0.2:
                self.state = GameState.MENU
                self.current_level = None
                self.current_difficulty_index = 0
                self._update_level_index_from_difficulty()
                self.led_state = "idle"
                self._game_over_button_press_time = 0
                self._play_sound("menu_select")
        
        if not button_current and self._game_over_button_last_state:
            self._game_over_button_press_time = 0
        
        self._game_over_button_last_state = button_current
    
    def _update_paused(self):
        """Update paused state"""
        # Game is paused - wait for resume
        pass
    
    def _update_inputs(self, current_time):
        """Update input processing"""
        # Encoder input (only in playing state)
        if self.state == GameState.PLAYING and ENCODER_AVAILABLE:
            try:
                encoder_pos = encoder.position
            except:
                encoder_pos = self.last_encoder_position
            
            if encoder_pos != self.last_encoder_position:
                diff = encoder_pos - self.last_encoder_position
                if abs(diff) <= 100 and diff != 0:
                    if diff > 0:
                        self.encoder_action_pending = ("rotate_right", current_time + RESPONSE_DELAY)
                    else:
                        self.encoder_action_pending = ("rotate_left", current_time + RESPONSE_DELAY)
                    self.last_encoder_position = encoder_pos
        
        # Check pending encoder action
        if self.encoder_action_pending:
            action, action_time = self.encoder_action_pending
            if current_time >= action_time:
                if self.state == GameState.PLAYING:
                    try:
                        self._check_cut_action(action)
                    except:
                        pass
                self.encoder_action_pending = None
        
        # Accelerometer input (skip if power switch is OFF to avoid I2C issues)
        if power_switch:
            try:
                if power_switch.value:  # HIGH = Switch OFF
                    return  # Skip accelerometer when switch is OFF
            except:
                pass
        
        if current_time - self.last_accel_action_time > 0.1:
            try:
                x, y, z = accelerometer.acceleration
                accel_threshold = 2.0
                
                if y > accel_threshold and self.last_accel_y <= accel_threshold:
                    self.accel_action_pending = ("forward", current_time + RESPONSE_DELAY)
                elif y < -accel_threshold and self.last_accel_y >= -accel_threshold:
                    self.accel_action_pending = ("backward", current_time + RESPONSE_DELAY)
                
                self.last_accel_y = y
                self.last_accel_action_time = current_time
            except:
                pass
        
        # Check pending accelerometer action
        if self.accel_action_pending:
            action, action_time = self.accel_action_pending
            if current_time >= action_time:
                if self.state == GameState.PLAYING:
                    try:
                        self._check_cut_action(action)
                    except:
                        pass
                self.accel_action_pending = None
    
    def _check_cut_action(self, action):
        """Check cut action"""
        current_time = time.monotonic()
        adjusted_current_time = current_time - self.total_pause_time
        sliced_any = False
        
        for apple in self.apples:
            if apple.sliced or apple.expired:
                continue
            
            if not apple.entered_valid_zone:
                continue
            
            if not apple.is_in_valid_zone():
                continue
            
            if apple.expected_action == action:
                if apple.valid_zone_entry_time is not None:
                    time_since_entry = adjusted_current_time - apple.valid_zone_entry_time
                    if 0 <= time_since_entry <= CUT_TIME_LIMIT:
                        apple.sliced = True
                        self.sliced_count += 1
                        sliced_any = True
                        self.led_state = "success"
                        self.last_led_update = current_time
                        self._play_sound("success")
                        break
        
        if not sliced_any and self.state == GameState.PLAYING:
            self.led_state = "error"
            self.last_led_update = current_time
            self._play_sound("error")
    
    def _play_sound(self, sound_type):
        """Play sound effect"""
        if not buzzer_available or not buzzer:
            return
        
        # Don't play sounds during hardware initialization
        if not hasattr(self, 'game_start_time'):
            return
        
        try:
            if buzzer_is_active:
                # Active buzzer - simple ON/OFF (non-blocking)
                if sound_type == "success":
                    if BUZZER_INVERTED_LOGIC:
                        buzzer.value = False
                    else:
                        buzzer.value = True
                elif sound_type == "error":
                    if BUZZER_INVERTED_LOGIC:
                        buzzer.value = False
                    else:
                        buzzer.value = True
                elif sound_type in ["start", "menu_select"]:
                    if BUZZER_INVERTED_LOGIC:
                        buzzer.value = False
                    else:
                        buzzer.value = True
                elif sound_type == "menu_move":
                    # Skip menu move sound to avoid blocking
                    pass
                elif sound_type == "game_over":
                    if BUZZER_INVERTED_LOGIC:
                        buzzer.value = False
                    else:
                        buzzer.value = True
            else:
                # Passive buzzer - PWM tones (non-blocking)
                if sound_type == "success":
                    buzzer.frequency = 2000
                    buzzer.duty_cycle = 32768
                elif sound_type == "error":
                    buzzer.frequency = 500
                    buzzer.duty_cycle = 32768
                elif sound_type in ["start", "game_over", "menu_select"]:
                    buzzer.frequency = 1500
                    buzzer.duty_cycle = 32768
                elif sound_type == "menu_move":
                    # Skip menu move sound
                    pass
        except:
            pass
    
    def _stop_sound(self):
        """Stop buzzer sound"""
        if not buzzer_available or not buzzer:
            return
        
        try:
            if buzzer_is_active:
                if BUZZER_INVERTED_LOGIC:
                    buzzer.value = True
                else:
                    buzzer.value = False
            else:
                buzzer.duty_cycle = 0
        except:
            pass
    
    def _update_leds(self, current_time):
        """Update LED state"""
        try:
            if self.led_state == "idle" or self.led_state == "game_over":
                # Slow breathing blue
                if not hasattr(self, '_last_led_brightness_update'):
                    self._last_led_brightness_update = current_time
                
                # Update brightness every frame
                self.led_brightness += 0.005 * self.led_brightness_dir
                if self.led_brightness >= 0.5:
                    self.led_brightness = 0.5
                    self.led_brightness_dir = -1
                elif self.led_brightness <= 0.1:
                    self.led_brightness = 0.1
                    self.led_brightness_dir = 1
                
                pixels.brightness = self.led_brightness
                pixels[0] = (0, 0, 255)
                self._last_led_brightness_update = current_time
                self._stop_sound()
            
            elif self.led_state == "playing":
                # Solid green
                pixels.brightness = 0.3
                pixels[0] = (0, 255, 0)
                self._stop_sound()
            
            elif self.led_state == "success":
                # Quick blue flash
                if current_time - self.last_led_update < 0.2:
                    pixels.brightness = 0.5
                    pixels[0] = (0, 0, 255)
                else:
                    pixels.brightness = 0.3
                    pixels[0] = (0, 255, 0)
                    self._stop_sound()
                    if current_time - self.last_led_update > 0.3:
                        self.led_state = "playing"
            
            elif self.led_state == "error":
                # Quick red flash
                if current_time - self.last_led_update < 0.2:
                    pixels.brightness = 0.5
                    pixels[0] = (255, 0, 0)
                else:
                    pixels.brightness = 0.3
                    pixels[0] = (0, 255, 0)
                    self._stop_sound()
                    if current_time - self.last_led_update > 0.3:
                        self.led_state = "playing"
            
            elif self.led_state == "warning":
                # Blink yellow/orange
                blink = int(current_time * 3) % 2
                pixels.brightness = 0.4
                if blink:
                    pixels[0] = (255, 165, 0)
                else:
                    pixels[0] = (255, 255, 0)
        except:
            pass
    
    def draw(self):
        """Draw game screen"""
        if not display_ok or not display:
            return
        
        # Check if OLED should be off FIRST (before any display operations)
        if power_switch:
            try:
                current_switch_state = read_pin_stable(power_switch)
                if current_switch_state:  # HIGH = Switch OFF
                    return  # Don't touch display at all
            except:
                pass
        
        oled_should_be_off = getattr(display, '_oled_should_be_off', False)
        if oled_should_be_off:
            return  # Don't touch display at all
        
        try:
            display.fill(0)
            
            if self.current_level is None:
                self.state = GameState.MENU
            
            if self.state == GameState.MENU:
                self._draw_menu()
            elif self.state == GameState.PLAYING:
                if self.current_level is not None:
                    self._draw_playing()
                else:
                    self.state = GameState.MENU
                    self._draw_menu()
            elif self.state == GameState.GAME_OVER:
                self._draw_game_over()
            else:
                self.state = GameState.MENU
                self.current_level = None
                self._draw_menu()
            
            display.show()
        except:
            pass
    
    def _draw_menu(self):
        """Draw menu - show difficulty selection"""
        try:
            if self.current_difficulty_index < len(DIFFICULTY_NAMES):
                difficulty_name = DIFFICULTY_NAMES[self.current_difficulty_index]
                
                # Draw difficulty name
                draw_text(display, difficulty_name, 40, 10, 1, spacing=6)
                
                # Draw difficulty selection indicators
                bar_y = 25
                bar_height = 8
                bar_width = 25
                spacing = 35
                
                for i in range(len(DIFFICULTY_NAMES)):
                    x = 20 + i * spacing
                    if i == self.current_difficulty_index:
                        display.fill_rect(x, bar_y, bar_width, bar_height, 1)
                    else:
                        display.rect(x, bar_y, bar_width, bar_height, 1)
                
                # Show level info
                if self.current_level_index < len(LEVELS):
                    level = LEVELS[self.current_level_index]
                    level_info = level["name"]
                    draw_text(display, level_info, 10, 40, 1, spacing=5)
                
                # Draw hint
                draw_text(display, "PRESS START", 20, 55, 1, spacing=6)
        except:
            pass
    
    def _draw_playing(self):
        """Draw playing screen"""
        try:
            if self.current_level:
                # Draw status bar
                display.fill_rect(0, 0, OLED_WIDTH, 12, 0)
                
                # Level name
                level_name = self.current_level["name"]
                short_name = level_name[:6] if len(level_name) > 6 else level_name
                draw_text(display, short_name, 2, 2, 1, spacing=5)
                
                # Score
                total_apples = self.current_level["apples"]
                score_text = f"{self.sliced_count}/{total_apples}"
                draw_text(display, score_text, 45, 2, 1, spacing=5)
                
                # Countdown
                current_time = time.monotonic()
                adjusted_current_time = current_time - self.total_pause_time
                elapsed = adjusted_current_time - self.game_start_time
                remaining = max(0, self.current_level["time"] - elapsed)
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                time_text = f"{minutes}:{seconds:02d}"
                draw_text(display, time_text, 85, 2, 1, spacing=5)
                
                # Time indicator dots
                time_dots = min(int(remaining / 5), 20)
                for i in range(time_dots):
                    display.pixel(OLED_WIDTH - 5 - i, 5, 1)
            
            # Draw apples (max 10)
            apple_count = 0
            for apple in self.apples:
                if apple_count >= 10:
                    break
                if not apple.sliced and not apple.expired:
                    x, y = apple.get_pos()
                    if 0 <= x < OLED_WIDTH and 0 <= y < OLED_HEIGHT:
                        display.fill_rect(int(x), int(y), APPLE_SIZE[0], APPLE_SIZE[1], 1)
                        apple_count += 1
        except:
            pass
    
    def _draw_game_over(self):
        """Draw game over screen"""
        try:
            draw_text(display, "GAME OVER", 25, 20, 1, spacing=5)
            
            if self.current_level:
                total_apples = self.current_level["apples"]
                score_text = f"{self.sliced_count}/{total_apples}"
                draw_text(display, score_text, 40, 35, 1, spacing=5)
            
            draw_text(display, "PRESS RESTART", 15, 50, 1, spacing=4)
        except:
            pass

# ==================== Main Loop ====================

def main():
    print("\n" + "=" * 50)
    print("Game started - entering main loop")
    print("=" * 50)
    # Show welcome screen
    if display:
        try:
            display.fill(0)
            draw_text(display, "WELCOME", 25, 25, 1, spacing=6)
            display.show()
            time.sleep(2)
        except Exception as e:
            print(f"Welcome screen display error: {e}")
    
    print("[Control Instructions]")
    print("  - Rotary encoder: Select difficulty (Easy/Medium/Hard)")
    print("  - Long press button (1 second): Start game")
    print("  - Tilt forward/backward: Slice apples from top/bottom")
    print("  - Rotate encoder (in game): Slice apples from left/right")
    print("  - Short press button (in game): Restart")
    print("=" * 50)
    
    # Create game instance
    game = Game()
    
    # Initial draw
    if display:
        try:
            game.draw()
        except:
            pass
    
    last_draw_time = time.monotonic()
    last_debug_time = time.monotonic()
    
    try:
        while True:
            current_time = time.monotonic()
            
            # Output debug info every 5 seconds
            if current_time - last_debug_time > 5.0:
                print(f"[Status] Game state: {game.state}, "
                      f"Difficulty: {DIFFICULTY_NAMES[game.current_difficulty_index] if game.current_difficulty_index < len(DIFFICULTY_NAMES) else 'N/A'}, "
                      f"Apples sliced: {game.sliced_count}")
                last_debug_time = current_time
            
            # Update game state
            game.update()
            
            # Draw screen every 200ms to reduce flicker
            if current_time - last_draw_time > 0.2:
                try:
                    game.draw()
                    last_draw_time = current_time
                except Exception as e:
                    print(f"Draw error: {e}")
            
            # Small delay to reduce CPU usage
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("\nGame exited by user")
    except Exception as e:
        print(f"Fatal error in main loop: {e}")
        # Cleanup
        if display:
            try:
                display.fill(0)
                display.show()
            except:
                pass
        if pixels:
            try:
                pixels[0] = (0, 0, 0)
            except:
                pass
        if buzzer:
            try:
                if BUZZER_INVERTED_LOGIC:
                    buzzer.value = True
                else:
                    buzzer.value = False
            except:
                pass

if __name__ == "__main__":
    main()