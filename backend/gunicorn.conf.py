def post_worker_init(worker):
    import app as core
    from quality_deadlines import start_deadline_worker
    start_deadline_worker(vars(core))
