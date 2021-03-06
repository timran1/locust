import random
import math
from time import monotonic

def between(min_wait, max_wait):
    """
    Returns a function that will return a random number between min_wait and max_wait.

    Example::

        class MyUser(User):
            # wait between 3.0 and 10.5 seconds after each task
            wait_time = between(3.0, 10.5)
    """
    return lambda instance: min_wait + random.random() * (max_wait - min_wait)


def constant(wait_time):
    """
    Returns a function that just returns the number specified by the wait_time argument

    Example::

        class MyUser(User):
            wait_time = constant(3)
    """
    return lambda instance: wait_time


def constant_pacing(wait_time):
    """
    Returns a function that will track the run time of the tasks, and for each time it's
    called it will return a wait time that will try to make the total time between task
    execution equal to the time specified by the wait_time argument.

    In the following example the task will always be executed once every second, no matter
    the task execution time::

        class MyUser(User):
            wait_time = constant_pacing(1)
            @task
            def my_task(self):
                time.sleep(random.random())

    If a task execution exceeds the specified wait_time, the wait will be 0 before starting
    the next task.
    """

    def wait_time_func(self):
        if not hasattr(self, "_cp_last_run"):
            self._cp_last_wait_time = wait_time
            self._cp_last_run = monotonic()
            return wait_time
        else:
            run_time = monotonic() - self._cp_last_run - self._cp_last_wait_time
            self._cp_last_wait_time = max(0, wait_time - run_time)
            self._cp_last_run = monotonic()
            return self._cp_last_wait_time

    return wait_time_func

def constant_uniform(wait_time):
    """
    Returns a function that will track the run time of the tasks, and for each time it's 
    called it will return a wait time that will try to make the total time between task 
    execution equal to the time specified by the wait_time argument. The time between 
    tasks will be maintined.

    Statistically, a constant inter-arrival time between tasks will be maintained
    regardless of number of threads and workers, given that task run time is less than
    specified wait_time.
    
    In the following example the task will always be executed once every second, no matter 
    the task execution time. All the users will be synchronized to spread out the exact
    execution trigger over the entire second::
    
        class User(Locust):
            wait_time = constant_uniform(1)
            class task_set(TaskSet):
                @task
                def my_task(self):
                    time.sleep(random.random())
    
    If a task execution exceeds the specified wait_time, the wait will be 0 before starting 
    the next task.
    """
    def wait_time_func(self):

        locust_id = self.id
        n_users = self.environment.runner.user_count
        user_offset = wait_time / n_users * locust_id

        worker_offset = 0
        if (str(type(self.environment.runner)) == "<class 'locust.runners.WorkerRunner'>"):
            worker_offset = self.environment.runner.timeslot_ratio * wait_time / n_users

        wall_clock = monotonic() + worker_offset + user_offset
        since_last_trigger = wall_clock % wait_time

        time_remaining = max(0, wait_time - since_last_trigger)
        return time_remaining
    return wait_time_func

def poisson(lambda_value):
    """
    Returns a function that will track the run time of the tasks, and for each time it's 
    called it will return a wait time that will try to achieve a poisson distribution of
    tasks executions with lambda specified as lambda_value, given that task run time is
    less than specified lambda_value.
    
    Statistically, Locust will try to ensure:
        RPS                     = 1/lambda
        Inter-Arrival Mean      = 1/lambda
        Inter-Arrival Variance  = 1/(lambda^2)

    Note: A reasonably high number of tasks must be executed to achieve these statistics.

    In the following example, a poisson task distribution with lambda = 1 will be executed::
    
        class User(Locust):
            wait_time = poisson(1)
            class task_set(TaskSet):
                @task
                def my_task(self):
                    time.sleep(random.random())
    
    """

    # Notes on statistics:
    #   Poisson Arrival Time Distribution = Exponential Inter-Arrival Distribution
    wait_time = 1 / lambda_value

    def random_exponential(lambda_value):
        x = random.random()
        return lambda_value * math.exp(-lambda_value * x)

    def wait_time_func(self):

        locust_id = self.id
        n_users = self.environment.runner.user_count
        user_offset = wait_time / n_users * locust_id

        worker_offset = 0
        if (str(type(self.environment.runner)) == "<class 'locust.runners.WorkerRunner'>"):
            worker_offset = self.environment.runner.timeslot_ratio * wait_time / n_users

        next_trigger_target = random_exponential(lambda_value) + lambda_value

        wall_clock = monotonic() + worker_offset + user_offset
        since_last_trigger = wall_clock % wait_time

        time_remaining = max(0, next_trigger_target - since_last_trigger)
        return time_remaining
    return wait_time_func
