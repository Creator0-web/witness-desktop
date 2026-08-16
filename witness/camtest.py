"""Camera diagnostic. Run:  python camtest.py"""
print("1) Checking OpenCV...")
try:
    import cv2
    print(f"   OpenCV {cv2.__version__} imported OK")
    _ = cv2.CascadeClassifier(cv2.data.haarcascades +
                              "haarcascade_frontalface_default.xml")
    print("   Face detector loads OK")
except Exception as e:
    print(f"   BROKEN: {e}")
    print("   Fix: pip uninstall opencv-python -y")
    print("        pip install opencv-python --force-reinstall")
    print("   If that fails on Python 3.14, tell Claude — we'll install 3.12.")
    raise SystemExit(1)

print("2) Looking for cameras on slots 0-2...")
found = False
for idx in (0, 1, 2):
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if cap.isOpened():
        ok, frame = cap.read()
        if ok:
            print(f"   Slot {idx}: WORKING camera, frame {frame.shape[1]}x"
                  f"{frame.shape[0]}")
            found = True
        else:
            print(f"   Slot {idx}: opens but gives no image "
                  "(check Windows camera privacy settings)")
        cap.release()
    else:
        print(f"   Slot {idx}: nothing")
if not found:
    print("   No working camera. Check: plugged in? Windows Settings -> "
          "Privacy & security -> Camera -> desktop apps allowed?")
else:
    print("All good — restart WITNESS and the dot should go red when it "
          "sees you.")
