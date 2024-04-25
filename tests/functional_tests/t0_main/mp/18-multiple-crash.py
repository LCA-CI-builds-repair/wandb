#!/usr/bin/env python
try:
    run.finish()
except Exception as e:
    logging.error(f"An error occurred while running the finish function: {e}")


def process_child(n: int, main_q: mp.Queue, proc_q: mp.Queue):
    print(f"init:{n}")
    run = wandb.init(config=dict(id=n))

    # let main know we have called init
    main_q.put(n)
    proc_q.get()

    run.log({"data": n})

    # let main know we have called log
    main_q.put(n)
    proc_q.get()

    if n == 2:
        # Triggers a FileNotFoundError from the internal process
        # because the internal process reads/writes to the current run directory.
        shutil.rmtree(run.dir)

    # let main know we have crashed a run
    main_q.put(n)
    proc_q.get()

    run.finish()
    print(f"finish:{n}")


def main_sync(workers: List):
    for _, mq, _ in workers:
        mq.get()
    for _, _, pq in workers:
        pq.put(None)


def main():
    wandb.setup()

    workers = []
    for n in range(4):
        main_q = mp.Queue()
        proc_q = mp.Queue()
        p = mp.Process(
            target=process_child, kwargs=dict(n=n, main_q=main_q, proc_q=proc_q)
        )
        workers.append((p, main_q, proc_q))

    for p, _, _ in workers:
        p.start()

    # proceed after init
    main_sync(workers)

    # proceed after log
    main_sync(workers)

    # proceed after crash
    main_sync(workers)

    for p, _, _ in workers:
        p.join()

    print("done")


if __name__ == "__main__":
    main()
