import pyautogui

im1 = pyautogui.screenshot(region=(1765, 1026, 120, 50))#region=(150,800,1200,280))
im1.save(r"./region.png")