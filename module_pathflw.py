import sensor, image, time, pyb
from pid import PID

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QQVGA)
#VGA:640X480 QVGA：320X240 QQVGA:160X120 QQQVGA:80X60 QQQQVGA:40X30  飞行方向↑
sensor.skip_frames(time = 2000)
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)
uart = pyb.UART(3, 500000, timeout_char = 1000)
C = ord('C') #逆时针
F = ord('F') #顺时针
G = ord('G') #前进
B = ord('B') #后退
R = ord('R') #右
L = ord('L') #左
D = ord('D') #下降
U = ord('U') #上升
E = ord('E') #降落
S = ord('S') #停止
H = ord('H') #允许控制
red_led   = pyb.LED(1)
green_led = pyb.LED(2)
blue_led  = pyb.LED(3)
clock = time.clock()

flagHoverHeight = 1 # 开始定高标志位
flagStartCrclDect = 0 # 开始寻找起飞位置
flagHoverOnCrclTime = 0 # 开始悬停计时
flagStartTiming = 0 # 未计时标志位
flagPathFollowing = 0 # 开始循迹

HOVERTIME = 15000 # 最大停留时间
HOVERTH = (0.06, 0.08) # 认为悬停在中心的阈值(width, height) ,越小越苛刻
PATHTH = (18, 71, -20, 11, -10, 27)
height_pid = PID(p=0.7, i=0, imax=90) # 优先水平方向对齐
width_pid = PID(p=0.7, i=0, imax=90)  # 再垂直方向对齐

def send_direction_packet(direct, velocity): # 封包函数，只取八位
    s = 0xAA + 0x8C + direct + (int(velocity/256)) + (int(velocity%256))
    s = int(s % 256)
    temp_flow = struct.pack("<BBBhB", 0xAA, 0x89, 03, direct, velocity, s)
    uart.write(temp_flow)

# ---------已经达到悬停高度，开始找起飞点-----------
class crdOfCrcl:
    def __init__(self, x=0, y=0, r=0):
        self.x = x
        self.y = y
        self.r = r

crd_crcl = crdOfCrcl(x=0, y=0, r=0) # 初始化圆的参数

while(True):
    clock.tick()
    # img = sensor.snapshot().lens_corr(strength = 1.8)
    img = sensor.snapshot().lens_corr(strength = 1.8).binary([PATHTH], invert = True)
    line = img.get_regression([(100, 100)], robust = True)
    img.draw_rectangle(20, 20, 120, 80, color = [0, 255, 0])
    print(line)
    if line:
        img.draw_line(line.x1(), line.y1(), line.x2(), line.y2(), color = [255, 0 ,0])
