class DexterityExercise:

    def __init__(self):

        self.state = "OPEN"

        self.repetitions = 0

    def update(self, finger_count):

        if finger_count >= 4:

            current = "OPEN"

        elif finger_count <= 1:

            current = "CLOSED"

        else:

            return

        if self.state == "OPEN" and current == "CLOSED":

            self.repetitions += 1

        self.state = current
