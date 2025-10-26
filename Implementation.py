import hashlib
import secrets
import random
import numpy as np
import matplotlib.pyplot as plt

# ======================================================
#  Hash functions
# ======================================================

def sha2_hash(data: bytes) -> bytes:
    # SHA-256 -> 256 bits
    return hashlib.sha256(data).digest()

def sha3_hash(data: bytes) -> bytes:
    # SHA3-512 -> 512 bits
    return hashlib.sha3_512(data).digest()

def ascon_hash_func(data: bytes) -> bytes:
    """
    TEMPORARY STUB for ASCON.
    Replace with a real ASCON-hash implementation when you have it.
    Currently uses SHAKE256(256 bits) so pipeline works.
    """
    return hashlib.shake_256(data).digest(32)  # 32 bytes => 256 bits


# ======================================================
#  Helpers
# ======================================================

def bytes_to_bits(data: bytes) -> str:
    """Convert bytes -> string of '0'/'1' bits."""
    return ''.join(format(byte, '08b') for byte in data)

def hamming_distance(a_bits: str, b_bits: str) -> int:
    """Count positions where bits differ."""
    return sum(bit1 != bit2 for bit1, bit2 in zip(a_bits, b_bits))


# ======================================================
#  1. Hamming distance test + scatter plot
#     ("avalanche effect")
# ======================================================

def hamming_test(hash_func, num_samples=2000, msg_len_bytes=64):
    """
    Generate num_samples pairs:
      - random message
      - same message with exactly 1 flipped bit
    Compute Hamming distance between hash(msg) and hash(msg_mod).
    Return list of distances (in bits).
    """
    distances = []

    for _ in range(num_samples):
        msg = secrets.token_bytes(msg_len_bytes)

        # flip exactly one random bit in the message
        mod = bytearray(msg)
        flip_bit_index = random.randint(0, msg_len_bytes * 8 - 1)
        mod[flip_bit_index // 8] ^= (1 << (flip_bit_index % 8))

        h1_bits = bytes_to_bits(hash_func(msg))
        h2_bits = bytes_to_bits(hash_func(bytes(mod)))

        dist = hamming_distance(h1_bits, h2_bits)
        distances.append(dist)

    return distances


def plot_hamming(distances, name, outfile):
    """
    Scatter plot Hamming distance vs hash index
    with mean line and cleaned style.
    Saves plot to outfile (PNG).
    Returns mean distance.
    """
    x = list(range(1, len(distances) + 1))
    mean_val = np.mean(distances)

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.scatter(x, distances, s=4, color="black")
    ax.axhline(mean_val, color="black", linewidth=1)

    ax.set_xlabel("Hash number")
    ax.set_ylabel("Hamming distance")
    ax.set_title(f"{name} Hamming distance test")

    # clean top/right frame for more 'publication' look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(outfile, dpi=300)
    plt.close(fig)

    return mean_val


# ======================================================
#  2. Bit prediction test + publication-style plot
#     ("bit predictability" / randomness per bit position)
# ======================================================

def bit_prediction(hash_func, num_messages=1000, msg_len_bytes=64):
    """
    For each bit position i in the hash output:
      - estimate P(bit_i == 1) using num_messages random inputs
    Return:
      probs_per_bit : list of probabilities of '1' in %
      stats : dict {min,max,avg,sd} in %
    """
    # determine hash length in bits
    test_hash_bits = bytes_to_bits(hash_func(b"test"))
    n_bits = len(test_hash_bits)

    probs_per_bit = []

    for bit_index in range(n_bits):
        ones_count = 0
        for _ in range(num_messages):
            msg = secrets.token_bytes(msg_len_bytes)
            h_bits = bytes_to_bits(hash_func(msg))
            if h_bits[bit_index] == '1':
                ones_count += 1
        prob_1 = (ones_count / num_messages) * 100.0  # percentage
        probs_per_bit.append(prob_1)

    probs_arr = np.array(probs_per_bit)
    stats = {
        "min": float(np.min(probs_arr)),
        "max": float(np.max(probs_arr)),
        "avg": float(np.mean(probs_arr)),
        "sd":  float(np.std(probs_arr, ddof=1)),  # sample std dev
    }
    return probs_per_bit, stats


def plot_bit_prediction_pretty(probs_per_bit, name, outfile):
    """
    Publication-style bit prediction plot:
    - thin line for per-bit probability
    - dashed line at 50% (ideal)
    - solid line at measured average
    - zoomed Y range
    - legend
    - cleaned frame
    """
    probs_arr = np.array(probs_per_bit)
    n_bits = len(probs_arr)
    x = np.arange(1, n_bits + 1)

    avg_val = float(np.mean(probs_arr))

    fig, ax = plt.subplots(figsize=(8, 4))

    # curve: probability of '1' for each bit position
    ax.plot(x, probs_arr, linewidth=0.6, color="black", label="per-bit P(1)")

    # ideal value 50%
    ax.axhline(
        50.0,
        linestyle="--",
        linewidth=1,
        color="gray",
        label="50% ideal"
    )

    # measured average
    ax.axhline(
        avg_val,
        linestyle="-",
        linewidth=1,
        color="black",
        label=f"mean = {avg_val:.2f}%"
    )

    ax.set_xlabel("Bit number")
    ax.set_ylabel("Probability of 1 [%]")
    ax.set_title(f"{name} bits prediction")

    # dynamic but zoomed Y range around ~50%
    ymin = min(48.0, probs_arr.min() - 0.2)
    ymax = max(52.0, probs_arr.max() + 0.2)
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(1, n_bits)

    # clean frame (remove top/right)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # lightweight legend
    ax.legend(loc="upper left", frameon=False, fontsize=8)

    fig.tight_layout()
    fig.savefig(outfile, dpi=300)
    plt.close(fig)


# ======================================================
#  3. Runs test (test serii, Wald–Wolfowitz)
#     ("are 0/1 runs random-looking?")
# ======================================================

def runs_test(hash_func, num_samples=1000, msg_len_bytes=64):
    """
    For each random message:
      - get hash bits
      - count number of runs R (blocks of same bit)
      - compute expected runs R_bar, std dev SD
      - compute Z = (R - R_bar) / SD

    We then return the mean absolute Z across all samples.
    The closer mean |Z| is to 0, the closer the sequence
    looks to an i.i.d. Bernoulli(0.5) process.
    """
    z_values = []

    for _ in range(num_samples):
        msg = secrets.token_bytes(msg_len_bytes)
        bits = bytes_to_bits(hash_func(msg))

        n1 = bits.count('1')
        n0 = bits.count('0')

        # count runs: number of transitions + 1
        R = 1
        for i in range(1, len(bits)):
            if bits[i] != bits[i-1]:
                R += 1

        # expected number of runs under randomness
        R_bar = (2 * n1 * n0) / (n1 + n0) + 1

        # standard deviation of runs
        numerator = (2 * n1 * n0) * (2 * n1 * n0 - n1 - n0)
        denominator = ((n1 + n0) ** 2) * (n1 + n0 - 1)
        SD = np.sqrt(numerator / denominator) if denominator != 0 else 0.0

        Zstat = (R - R_bar) / SD if SD != 0 else 0.0
        z_values.append(abs(Zstat))

    return float(np.mean(z_values))


# ======================================================
#  Runner
# ======================================================

def run_all_for_function(name, func):
    print(f"\n===== {name} =====")

    # --- 1. Hamming test ---
    dists = hamming_test(func, num_samples=2000, msg_len_bytes=64)
    mean_hamming = plot_hamming(dists, name, f"hamming_{name}.png")
    ideal = len(bytes_to_bits(func(b'test'))) / 2
    print(
        f"[Hamming] avg distance = {mean_hamming:.2f} bits "
        f"(ideal ~ {ideal:.2f})"
    )
    print(f"[Hamming] plot -> hamming_{name}.png")

    # --- 2. Bit prediction test ---
    probs_per_bit, stats = bit_prediction(
        func,
        num_messages=1000,
        msg_len_bytes=64
    )
    plot_bit_prediction_pretty(
        probs_per_bit,
        name,
        f"bit_prediction_{name}.png"
    )
    print(
        f"[Bit prediction] min={stats['min']:.2f}  "
        f"max={stats['max']:.2f}  "
        f"avg={stats['avg']:.2f}  "
        f"sd=±{stats['sd']:.2f}"
    )
    print(f"[Bit prediction] plot -> bit_prediction_{name}.png")

    # --- 3. Runs test ---
    avg_abs_z = runs_test(func, num_samples=1000, msg_len_bytes=64)
    print(
        f"[Runs test] mean |Z| = {avg_abs_z:.3f} "
        "(im bliżej 0, tym bardziej losowy ciąg)"
    )


if __name__ == "__main__":
    hash_functions = {
        "SHA2-256": sha2_hash,
        "SHA3-512": sha3_hash,
        "ASCON-STUB": ascon_hash_func  # replace later with real ASCON
    }

    for name, func in hash_functions.items():
        run_all_for_function(name, func)
