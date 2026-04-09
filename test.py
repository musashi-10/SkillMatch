from ultralytics import YOLO


model = YOLO(r"C:\Users\VEDANT\runs\detect\train7\weights\best.pt")


results = model("food.jpg", show=True)


for r in results:
    print(r.names)