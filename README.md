# 2018NUEDC

# OPENMV 学习记录

## LED对应表

LED颜色与动作对应表

| LED(1)-红 | LED(2)-绿 | LED(3)-蓝 | 颜色 | 动作             |
| --------- | --------- | --------- | ---- | ---------------- |
| 0         | 0         | 0         | 空   |                  |
| 0         | 0         | 1         | 蓝色 |                  |
| 0         | 1         | 0         | 绿色 | 已到达悬停位置   |
| 0         | 1         | 1         | 青色 |                  |
| 1         | 0         | 0         | 红色 | 正在寻找悬停位置 |
| 1         | 0         | 1         | 紫色 | 发现火灾         |
| 1         | 1         | 0         | 黄色 | 循迹中           |
| 1         | 1         | 1         | 白色 |                  |

## PATHFOLLOW模块

该模块主要完成飞行器循迹飞行功能。飞行方式有两种，一种是绕边界飞行一圈后飞出，该飞行方式不可以解决火源位于中心的特殊情况。第二种是地毯式循迹飞行，该方式理论上可以识别到所有的火源，但是需要较长的时间，而且内部由于没有参考位置，容易飞歪。

综合以上考虑，虽然绕边界方法存在缺陷，但是实现起来较为容易，因此优先实现绕边界飞行的控制。

## 绕线飞行

在本小组的设置中，边界是由不超过5mm的黑色胶带黏贴在棕色纸板上建立的。首先需要通过OpenMV识别出边界，编写以下函数：

```micropython
        PATHTH = (0, 18, -10, 15, -15, 15)
        sensor.set_pixformat(sensor.RGB565)
        img = sensor.snapshot().lens_corr(strength = 1.8).binary([PATHTH])
```

其中**PATHTH**是元组列表对象，利用`.binary()`代码块来识别出图片中的线段。

<img src="C:\Users\asus1\AppData\Roaming\Typora\typora-user-images\image-20210726103039993.png" alt="image-20210726103039993" style="zoom:50%;" /><img src="C:\Users\asus1\AppData\Roaming\Typora\typora-user-images\image-20210726103106129.png" alt="image-20210726103106129" style="zoom:50%;" />



利用设定阈值来识别出图像中的黑色轨迹线。

<img src="C:\Users\asus1\AppData\Local\Temp\WeChat Files\e58c4ca7301abb3736debe92dff2eaa.jpg" alt="e58c4ca7301abb3736debe92dff2eaa" style="zoom:50%;" />

在飞行过程中可能会遇到以上五种情况，由于首先采用的是绕线飞行的方式，所以会把整个过程分为三个部分。利用`get_regression()` 返回的直线斜率来决定某一阶段的飞行方式。但在此需要有一个假设：

> 假设：无人机的飞行不存在自偏航的可能

换句话说，就是无人机不会飞着飞着自己偏航了，这显然不现实，但为了从简单入手，先忽略了这个情况。当无人机完成了定点后，无人机默认向前飞行。此时无人机开始逐渐检测到图上图一的直线情况。此时回归直线（红线）的角度为0度左右，无人机此时需要调整自身的角度令其保持在整个视野偏右的部分来尽可能多的检测视野内的火灾情况。在飞行过程中还需要调整飞机中心点与拟合直线的距离在一个合适的范围内。`line_regression` 返回的`rho()` 和`theta()` 。<img src="C:\Users\asus1\AppData\Local\Temp\WeChat Files\39e3b196b572b46582ebeb473cfdf94.jpg" alt="39e3b196b572b46582ebeb473cfdf94" style="zoom:50%;" />

利用`line_regression`得到的结果如上图所示，其中第三区域并没有用到，只用到了1，2，4这三个区域的圆的切线所产生的直线。在循迹飞行过程中，无人机的OpenMV视野中将会按顺序出现以下几种情况：

<img src="C:\Users\asus1\AppData\Local\Temp\WeChat Files\5fba1a74dd87acbffa13a916062aa3a.jpg" alt="5fba1a74dd87acbffa13a916062aa3a" style="zoom:50%;" />

根据飞行过程将会按顺序出现以上七种情况，每一种情况都可以建立与之相符合的标志位来判定当前状态。假设在飞行过程中存在寻找到火源的可能，一共有八种动作状态，用表格形式展示为：

| 状态       | $\rho$   | $\theta$    | 动作                     |
| ---------- | -------- | ----------- | ------------------------ |
| 起飞识别   | >0(较大) | <90         | 未定                     |
| 前进飞行   | >0(较大) | $\approx0$  | 保持前进，保持右侧距离   |
| 左转识别   | >0       | >270        | 未定，暂定进行状态切换   |
| 左飞       | >0       | $\approx90$ | 保持左飞，保持上侧距离   |
| 后飞识别   | >0(较小) | <90         | 未定，暂定进行状态切换   |
| 后飞       | >0(较小) | $\approx0$  | 保持后飞，保持左侧距离   |
| 飞出区域   | >0       | >90         | 直线飞出                 |
| 检测到火源 |          |             | 中断，前往火源处执行灭火 |

## status与前进方式

+ status 0：还未识别到进入巡线

  以`send_direction_packet(G, 15) ` 的前进速度前进，直到`ROIPLACE_MID` 中的`get_regression`产生的`line`的角度是否在90度左右







## 地毯扫描式

地毯扫描式从起飞开始



## 飞行实验

### 实验一  验证从高速降为悬停会不会产生自振动

+ 验证方式：

  ```python
  while(True):
      while(flag):
          if uart.any():
              if uart.readchar() == H:
                  flag = 0
  
      green_led.on()
      send_direction_packet(G, velocity[0])
      pyb.delay(5000)
      green_led.off()
  
      green_led.on()
      send_direction_packet(S, 0)
      pyb.delay(5000)
      green_led.off()
  
  
      green_led.on()
      send_direction_packet(B, velocity[0])
      pyb.delay(5000)
      green_led.off()
  
      green_led.on()
      send_direction_packet(S, 0)
      pyb.delay(5000)
      green_led.off()
  
      send_direction_packet(E, 0)
  ```

  以15cm/s速度前进2s后悬停5s然后再以15cm/s速度后退2s后悬停5s

  + 实验结果：15cm/s的速度不会使得悬停后有较大的改变

