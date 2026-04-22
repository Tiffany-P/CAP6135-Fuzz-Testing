import os
import random
import subprocess
import time
import re

TARGET = "./jpeg2bmp"
SEED = "cross.jpg"
CRASH_DIR = "crashes"
OTHER_CRASH_DIR = "crashes/other"
OUT_DIR = "outputs"

# handles Bug#2 or Bug #2
BUG_RE = re.compile(r"Bug\s*#\s*(\d+)", re.IGNORECASE)

# Track stats
bug_counts = {i: 0 for i in range(1, 11)}
saved_bug = {i: False for i in range(1, 11)}

SAFE_START = 100

def mutate(data: bytearray) -> bytearray:
    m = bytearray(data)
    
    # randomly choose number of edits to do to file
    r = random.random()

    if r < 0.70:
        edits = random.randint(1, 3)
    elif r < 0.95:
        edits = random.randint(4, 12)
    else:
        edits = random.randint(20, 60)

    for _ in range(edits):
        if len(m) == 0:
            break

        choice = random.random()

        # Choose index avoiding first SAFE_START bytes if possible
        if len(m) > SAFE_START:
            i = random.randrange(SAFE_START, len(m))
        else:
            i = random.randrange(len(m))


        if choice < 0.15:
            # Overwrite a chunk
            block_len = random.randint(4, 128)
            start = random.randrange(SAFE_START, len(m)) if len(m) > SAFE_START else 0
            end = min(len(m), start + block_len)
            for j in range(start, end):
                m[j] = random.randrange(256)
        
        elif choice < 0.25:
            # Duplicate chunk
            if len(m) > SAFE_START + 50:
                a = random.randrange(SAFE_START, len(m) - 1)
                b = min(len(m), a + random.randint(10, 80))
                chunk = m[a:b]
                ins = random.randrange(SAFE_START, len(m))
                m[ins:ins] = chunk

        elif choice < 0.5:
            # Overwrite one byte
            m[i] = random.randrange(256)

        elif choice < 0.75:
            # Flip one random bit
            bit = 1 << random.randrange(8)
            m[i] ^= bit

        elif choice < 0.9:
            # Delete a byte
            if len(m) > 1:
                del m[i]

        else:
            # Insert random byte
            m.insert(i, random.randrange(256))

    return m


def run_one(mut_path: str, bmp_path: str):
    try:
        proc = subprocess.run(
            [TARGET, mut_path, bmp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=2
        )
    except subprocess.TimeoutExpired:
        return (None, True, "TIMEOUT")

    stderr = proc.stderr.decode("utf-8", errors="replace")

    match = BUG_RE.search(stderr)
    bug_num = int(match.group(1)) if match else None

    crashed = (proc.returncode != 0)

    return (bug_num, crashed, stderr)


def main():
    os.makedirs(CRASH_DIR, exist_ok=True)
    os.makedirs(OTHER_CRASH_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(SEED, "rb") as f:
        seed = bytearray(f.read())

    iterations = 0
    start = time.time()

    try:
        while True:
            iterations += 1

            mutated = mutate(seed)

            mut_path = f"mut_{iterations}.jpg"
            bmp_path = os.path.join(OUT_DIR, f"out_{iterations}.bmp")

            with open(mut_path, "wb") as f:
                f.write(mutated)

            bug_num, crashed, stderr = run_one(mut_path, bmp_path)

            # If labeled bug
            if bug_num in bug_counts:
                bug_counts[bug_num] += 1

                if not saved_bug[bug_num]:
                    save_path = os.path.join(CRASH_DIR, f"test-{bug_num}.jpg")
                    os.replace(mut_path, save_path)
                    saved_bug[bug_num] = True
                    print(f"[FOUND] Bug #{bug_num} -> saved {save_path}")
                else:
                    os.remove(mut_path)

            # Crash but no Bug# detected
            elif crashed:
                save_path = os.path.join(OTHER_CRASH_DIR, f"crash_{iterations}.jpg")
                os.replace(mut_path, save_path)
                print(f"[CRASH no Bug#] saved {save_path}")

            else:
                os.remove(mut_path)

            # Status every 100 iterations
            if iterations % 100 == 0:
                elapsed = time.time() - start
                found = sum(saved_bug.values())
                print(f"[{iterations} iters | {elapsed:.1f}s] unique bugs found: {found}/10")

            if time.time() - start > 600:
                print("reached 10 minutes")
                break


    except KeyboardInterrupt:
        print("\n[STOPPED BY USER]")

    # Final Summary
    print("\n=== FINAL BUG COUNTS ===")
    for i in range(1, 11):
        print(f"Bug #{i}: triggered {bug_counts[i]} times | saved={saved_bug[i]}")


if __name__ == "__main__":
    main()
