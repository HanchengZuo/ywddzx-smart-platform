def post_worker_init(worker):
    import app as core
    from quality_deadlines import start_deadline_worker
    start_deadline_worker(vars(core))
    from web_push_worker import start_push_worker
    start_push_worker(core.get_db_connection, core.app.config['SECRET_KEY'], core.app.logger)
