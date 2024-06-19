from celery.signals import task_postrun, task_prerun


@task_prerun.connect()
def task_pre_run(
    signal=None, sender=None, task_id=None, task=None, args=None, **kwargs
):
    print(
        "pre-run of add. Do special add things here. Task: {0}  sender: {1}".format(
            task, sender
        )
    )


@task_postrun.connect()
def task_post_run(
    signal=None,
    sender=None,
    task_id=None,
    task=None,
    args=None,
    retval=None,
    state=None,
    **kwargs
):
    # note that this hook runs even when there has been an exception thrown by the task
    print("post run {0} ".format(task))
