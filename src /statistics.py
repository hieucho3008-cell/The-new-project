import time

class Statistics:

    def __init__(self):

        self.start_time = time.time()

    def elapsed_time(self):

        return round(
            time.time() - self.start_time,
            2
        )

    def average_speed(self, reps):

        t = self.elapsed_time()

        if reps == 0:
            return 0

        return round(t / reps, 2)
