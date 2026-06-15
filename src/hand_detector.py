import cv2
import mediapipe as mp

class HandDetector:

    def __init__(self):

        self.mpHands = mp.solutions.hands

        self.hands = self.mpHands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )

        self.mpDraw = mp.solutions.drawing_utils

    def find_hands(self, img):

        imgRGB = cv2.cvtColor(
            img,
            cv2.COLOR_BGR2RGB
        )

        results = self.hands.process(imgRGB)

        allHands = []

        if (
            results.multi_hand_landmarks
            and
            results.multi_handedness
        ):

            h, w, _ = img.shape

            for handedness, handLms in zip(
                results.multi_handedness,
                results.multi_hand_landmarks
            ):

                lmList = []
                xList = []
                yList = []

                for lm in handLms.landmark:

                    cx = int(lm.x * w)
                    cy = int(lm.y * h)

                    lmList.append((cx, cy))

                    xList.append(cx)
                    yList.append(cy)

                centerX = sum(xList) // len(xList)
                centerY = sum(yList) // len(yList)

                handLabel = (
                    handedness
                    .classification[0]
                    .label
                )

                # Đảo lại vì camera đã flip
                if handLabel == "Left":
                    handLabel = "Right"
                else:
                    handLabel = "Left"

                handInfo = {
                    "lmList": lmList,
                    "center": (centerX, centerY),
                    "type": handLabel
                }

                allHands.append(handInfo)

                self.mpDraw.draw_landmarks(
                    img,
                    handLms,
                    self.mpHands.HAND_CONNECTIONS
                )

                cv2.putText(
                    img,
                    handLabel,
                    (centerX - 40, centerY - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0,255,0),
                    2
                )

        return allHands, img
