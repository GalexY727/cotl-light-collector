import pyautogui
import time

time.sleep(1)
im1 = pyautogui.screenshot(region=(1070, 762, 81, 93))#region=(150,800,1200,280))
im1.save(r"./region.png")