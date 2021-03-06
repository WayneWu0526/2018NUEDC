# Take Off and Path Following - By: JamesWu - 周二 7月 20 2021

import sensor, image, time, pyb, network, usocket, sys, struct, math
from pid import PID

sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
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
HongWai = pyb.Pin("P9", pyb.Pin.OUT_PP)
Bizzar = pyb.Pin("P6", pyb.Pin.OUT_PP)

flagHoverHeight = 0 # 开始定高标志位
flagStartCrclDect = 0 # 开始寻找起飞位置
flagPathFollowing = 1 # 开始循迹
networkStart = 0 # 开启网络回传

def Bizzar_ON():
    Bizzar.value(0)

def Bizzar_OFF():
    Bizzar.value(1)

def Hongwai_ON():
    HongWai.value(0)

def Hongwai_OFF():
    HongWai.value(1)

def send_direction_packet(direct, velocity): # 封包函数，只取八位
    s = 0xAA + 0x8C + direct + (int(velocity/256)) + (int(velocity%256))
    s = int(s % 256)
    temp_flow = struct.pack("<BBBBhB", 0xAA, 0x89, 03, direct, velocity, s)
    uart.write(temp_flow)

def send_direction_packet_yaw(direct, velocity): # 封包函数，只取八位
    s = 0xAA + 0x98 + 03 + direct + (int(velocity/256)) + (int(velocity%256))
    s = int(s % 256)
    temp_flow = struct.pack("<BBBBhB", 0xAA, 0x98, 03, direct, velocity, s)
    uart.write(temp_flow)

def saturation(inputValue, thresholds):
    if abs(inputValue) >= thresholds:
        return thresholds
    else:
        return abs(int(inputValue))

def line_to_cos_rho(line):
    if line.rho() <0: # 3|4象限
        return math.cos(math.radians(270 - line.theta())), -line.rho()
    else:
        if line.theta() > 90:
            return math.cos(math.radians(270 - line.theta())), line.rho()
        else:
            return math.cos(math.radians(90 - line.theta())), line.rho()

Bizzar_OFF()
Hongwai_OFF()
#.....................WIFI图传....................................#
#................................................................#
if networkStart:
    socket_success = 0
    SSID ='OPENMV_AP'    # Network SSID
    KEY  ='1234567890'    # Network key (must be 10 chars)
    HOST = ''           # Use first available interface
    PORT = 8080         # Arbitrary non-privileged port
    wlan = network.WINC(mode=network.WINC.MODE_AP)
    wlan.start_ap(SSID, key=KEY, security=wlan.WEP, channel=2)

    def send_frame(frame):
        cframe = frame.compressed(quality=50)
        header = "\r\n--openmv\r\n" \
                 "Content-Type: image/jpeg\r\n"\
                 "Content-Length:"+str(cframe.size())+"\r\n\r\n"
        client.send(header)
        client.send(cframe)

    while (socket_success == 0):
        red_led.on()
        pyb.delay(500)
        red_led.off()
        pyb.delay(500)
        # Create server socket
        s = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
        try:
            # Bind and listen
            s.bind([HOST, PORT])
            s.listen(5)

            # Set server socket timeout
            # NOTE: Due to a WINC FW bug, the server socket must be closed and reopened if
            # the client disconnects. Use a timeout here to close and re-create the socket.
            s.settimeout(3)
            print ('Waiting for connections..')
            client, addr = s.accept()
            # set client socket timeout to 2s
            client.settimeout(2.0)
            print ('Connected to ' + addr[0] + ':' + str(addr[1]))

            # Read request from client
            data = client.recv(1024)
            # Should parse client request here

            # Send multipart header
            client.send("HTTP/1.1 200 OK\r\n" \
                        "Server: OpenMV\r\n" \
                        "Content-Type: multipart/x-mixed-replace;boundary=openmv\r\n" \
                        "Cache-Control: no-cache\r\n" \
                        "Pragma: no-cache\r\n\r\n")
            # FPS clock
            # clock = time.clock()
            socket_success = 1
            continue
        except OSError as e:
            socket_success = 0
            s.close()
            print("socket error: ", e)

#-----------------------------------------------------------------------#
#-----------------------------------------------------------------------#

while(flagHoverHeight): # 开始定高
    blue_led.on()
    pyb.delay(500)
    blue_led.off()
    pyb.delay(500)
    if uart.readchar() == H:
       flagHoverHeight = 0 # 定高结束

#--------------总参数--------------#
MAXSPEED = 5
REACTIONTIME = 0 # 飞行器指令响应时间：REACTIONTIMEms
#--------------悬停参数--------------#
HOVERTIME = 15000 # 最大停留时间
HOVERTH = (0.09, 0.12, 0.06, 0.08) # [允许计时范围, 允许悬停范围] ,越小越苛刻
tolHoverTime = 0
flagStartTiming = 0 # 未计时标志位
height_pid = PID(p=0.8, i=0, imax=90) # 水平方向PID参数
width_pid = PID(p=0.8, i=0, imax=90)  # 垂直方向PID参数
yaw_pid = PID(p=0.8, i=0, imax=90)    # 偏航方向PID参数
#--------------循迹参数---------------#
PATHTH = (115, 255) # 识别直线的阈值
ROIPLACE_UP = (0, 12, 160, 8)
ROIPLACE_DOWN = (0, 100, 160, 8)
ROIPLACE_MID = (0, 32, 160, 56)
ROIPLACE_LEFT = (12, 0, 8, 120)
ROIPLACE_RIGHT = (140, 0, 8, 120)
LINE_RIGHT = (ROIPLACE_RIGHT[0] + ROIPLACE_RIGHT[2]/2, ROIPLACE_RIGHT[1],
    ROIPLACE_RIGHT[0] + ROIPLACE_RIGHT[2]/2, ROIPLACE_RIGHT[3])
status = 0

# -----------------进入主循环阶段-------------------
while(True):
    if  flagStartCrclDect: # 开始寻找起飞/降落位置
        img = sensor.snapshot().lens_corr(strength = 1.8)
        img.draw_rectangle(int((1/2-HOVERTH[0])*sensor.width()), int((1/2-HOVERTH[1])*sensor.height()),
          int(2*HOVERTH[0]*sensor.width()), int(2*HOVERTH[1]*sensor.height())) # 中心区域
        crcls = img.find_circles(threshold = 2600, x_margin = 10,
            y_margin = 10, r_margin = 2, r_min = 22, r_max = 30)
        if crcls: # 找到一个或多个圆
            circle = crcls[0]
            img.draw_circle(circle.x(), circle.y(), circle.r(), color = (255, 0, 0))
            img.draw_cross(circle.x(), circle.y(), color = (255, 0, 0))
            crcl_string = 'threshold:' + str(crcls[0][3]) + 'r:' + str(circle.r())
            img.draw_string(1, 1, crcl_string)
            # -----------------开始应用PID矫正位置------------------
            # if (在可接受的范围内)：悬停 else: 调整位置
            if(abs(circle.y() - sensor.height()/2) <= sensor.height()*HOVERTH[2] and
            abs(circle.x() - sensor.width()/2) <= sensor.width()*HOVERTH[3]):
                send_direction_packet(S, 0)
            else:
                width_error = (sensor.width()/2 - circle.x())*2/sensor.width()
                width_output = width_pid.get_pid(width_error, 20)
                print("水平移动速度：", saturation(width_output, MAXSPEED))
                if circle.x() > sensor.width()/2: # 应当往右飞
                    send_direction_packet(R, saturation(width_output, MAXSPEED))
                else: # 应当往左飞
                    send_direction_packet(L, saturation(width_output, MAXSPEED))
                pyb.delay(REACTIONTIME) # 留给飞行器REACTIONTIMEms的响应时间
                height_error = (sensor.height()/2 - circle.y())*2/sensor.height()
                height_output = height_pid.get_pid(height_error, 20)
                print("垂直移动速度：", saturation(height_output, MAXSPEED))
                if circle.y() > sensor.height()/2: # 应当往后飞
                    send_direction_packet(B, saturation(height_output, MAXSPEED))
                else: # 应当往前飞
                    send_direction_packet(G, saturation(height_output, MAXSPEED))
                pyb.delay(REACTIONTIME) # 留给飞行器REACTIONTIMEms的响应时间
            # -----------------判断是否悬停在起飞地点的上方并超过15秒--------------
            if(abs(circle.y() - sensor.height()/2) <= sensor.height()*HOVERTH[1] and
               abs(circle.x() - sensor.width()/2) <= sensor.width()*HOVERTH[0]):
                red_led.off()
                green_led.on()
                if(not flagStartTiming):
                    HoverTime = 0
                    start = pyb.millis()
                    flagStartTiming = 1
                else:
                   HoverTime = pyb.elapsed_millis(start)
                   if  HoverTime + tolHoverTime >= HOVERTIME:
                       flagStartTimig = 0  # 重置未计时标志位
                       flagStartCrclDect = 0 # 关闭起飞模块
                       flagPathFollowing = 1 # 开启循迹模块
                       # sensor.set_pixformat(sensor.RGB565)
                string = str(tolHoverTime + HoverTime)
            else: # 未到达目标区域
                if flagStartTiming :
                   HoverTime = pyb.elapsed_millis(start)
                   tolHoverTime += HoverTime
                green_led.off()
                red_led.on()
                start = pyb.millis() # 重置计时器
                flagStartTiming = 0 # 重置未计时标志位
                string = str(tolHoverTime)
            img.draw_string(80, 60, string, scale = 1)
        else: # 没有找到圆则悬停（后期改为按照某一规则移动）
            send_direction_packet(S, 0)

    # ------------------开始循迹-----------------------
    # GRAYSCALE下配合 PATHTH = (67, 170)
    # 进行二值化处理，在开启前需要关闭白平衡和自动增益。
    # sensor.set_auto_gain(False)
    # ensor.set_auto_whitebal(False)
    # 目前的结果发现首先利用GRAYSCALE再配合binary来实现将会更加稳定。
    # 再利用erode来进行噪点消除
    # 状态0：还未识别到中间位置
    # REACTIONTIME = 1000
    # img = sensor.snapshot().lens_corr(strength = 1.8)
    if flagPathFollowing:
        img = sensor.snapshot().lens_corr(strength = 1.8).binary([PATHTH], invert = True)
        img.erode(1, threshold = 3)
        if status == 0: # 前进到进入点
            send_direction_packet(S, 0) #悬停
            # send_direction_packet(G, MAXSPEED) # 以5cm/s的速度前进
            lines = img.find_lines(x_stride = 5, y_stride = 2, threshold = 2200,
                theta_margin = 10, rho_margin = 10)
            if lines:
                line = lines[0]
                cos, rho = line_to_cos_rho(line)
                yaw_error = 1 - abs(cos)
                yaw_output = yaw_pid.get_pid(yaw_error, 10)
                # 矫正偏航
                if cos > 0: # 无人机向前进方向右侧偏
                    send_direction_packet_yaw(F, saturation(yaw_output, MAXSPEED))
                    print('矫正方向：逆时针，偏航速度：', yaw_output)
                else:
                    send_direction_packet_yaw(C, saturation(yaw_output, MAXSPEED))
                    print('矫正方向：顺时针，偏航速度：', yaw_output)
                pyb.delay(REACTIONTIME)
            '''
            line = img.get_regression([(255, 255)], roi = ROIPLACE_DOWN, robust = True)
            stat_down = img.get_statistics([(0, 255)], roi = ROIPLACE_DOWN)
            if line:
                cos, rho = line_to_cos_rho(line)
                if abs(cos) >= 0.98 and stat_down.mean() > 110: # 已经前进到进入点
                    status = 1 # 正式进入循迹， 开始对齐右侧。
                    send_direction_packet(S, 0)
                    pyb.delay(REACTIONTIME) # 悬停一秒钟缓冲
            else:
                print(str(status) + '未找到线')
        elif status == 1: # 矫正进入点
            line = img.get_regression([(255, 255)], roi = ROIPLACE_MID, robust = True)
            if line: # 矫正横向进入位置
                # cos, rho = line_to_cos_rho(line)
                # if cos > 0.05: # 需要进行偏航矫正
                    # continue
                width_error = ((LINE_RIGHT[0] - (line.x1() + line.x2())/2))/80
                width_output = width_pid.get_pid(width_error, 10)
                if abs(width_error) < 8/80: # 右侧循迹线处于可接受范围
                    send_direction_packet(G, MAXSPEED) # 继续前进
                else:
                    send_direction_packet(G, 0) # 右侧循迹线处于不可接受范围
                    if width_error > 0:
                        send_direction_packet(R, saturation(width_output, MAXSPEED))
                    else:
                        send_direction_packet(L, saturation(width_output, MAXSPEED))
                    pyb.delay(REACTIONTIME)
                    # 暂时不考虑无人机在进行左右移动时会前后运动
                img.draw_line(line.x1(), line.y1(), line.x2(), line.y2(), color = 255)
            line = img.get_regression([(255, 255)], roi = ROIPLACE_UP, robust = True)
            stat_up = img.get_statistics([(0, 255)], roi = ROIPLACE_UP)
            if line and stat_up.mean()/255 >= 0.4: # 顶部已经检测到直线并且不是干扰
                status = 2
        elif status == 2: # 进入前进位置
            send_direction_packet(E, 0) # 降落
        string = 'status:' + str(status)
        img.draw_string(80, 60, string, color = 255, mono_space = False)
        img.draw_rectangle(ROIPLACE_UP)
        img.draw_rectangle(ROIPLACE_DOWN)
        img.draw_rectangle(ROIPLACE_MID)
        img.draw_rectangle(ROIPLACE_LEFT)
        img.draw_rectangle(ROIPLACE_RIGHT)
        '''
    if networkStart:
        send_frame(img) # WIFI发送实时图像
