import asyncio, logging, sys
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("probe")
def work():
    log.warning("warning from worker thread (asyncio imported, loop running in main thread)")
    return "ok"
async def main():
    r = await asyncio.to_thread(work)
    print("to_thread result:", r)
asyncio.run(main())
print("python", sys.version.split()[0], "-> no crash")
