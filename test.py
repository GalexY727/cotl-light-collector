import pyautogui
import keyboard
import time
from ahk import AHK

ahk = AHK()

def timer():
    start_time = time.time()
    try:
        region = (840, 0, 1087, 1800)
        pyautogui.locateOnScreen('./media/zenbook/candle.png', grayscale=1, region=region, confidence=.6)
        print("Found")
    except:
        pass
    print("--- %s seconds ---" % (time.time() - start_time))

def ss():
    region = (2192, 1701, 60, 60)
    pyautogui.screenshot(region=region).save('region.png')
    try: 
        pyautogui.locateOnScreen('./media/zenbook/q_info.png', grayscale=1, region=region, confidence=.9)
        print("Found")
    except:
        pass
        
if __name__ == '__main__':
    ss()