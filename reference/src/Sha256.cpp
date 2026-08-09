#include "Sha256.hpp"

#include <cstring>

namespace
{
constexpr u32 ROUND_CONSTANTS[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

u32 RotateRight(u32 value, u32 shift)
{
    return (value >> shift) | (value << (32 - shift));
}

u32 LoadBigEndian(const u8 *bytes)
{
    return static_cast<u32>(bytes[0]) << 24 | static_cast<u32>(bytes[1]) << 16 |
           static_cast<u32>(bytes[2]) << 8 | static_cast<u32>(bytes[3]);
}

void StoreBigEndian(u8 *bytes, u32 value)
{
    bytes[0] = static_cast<u8>(value >> 24);
    bytes[1] = static_cast<u8>(value >> 16);
    bytes[2] = static_cast<u8>(value >> 8);
    bytes[3] = static_cast<u8>(value);
}

bool DigestEquals(const Sha256Digest &digest, const u8 expected[32])
{
    return std::memcmp(digest.data(), expected, digest.size()) == 0;
}
} // namespace

Sha256::Sha256()
{
    this->Reset();
}

void Sha256::Reset()
{
    this->state[0] = 0x6a09e667;
    this->state[1] = 0xbb67ae85;
    this->state[2] = 0x3c6ef372;
    this->state[3] = 0xa54ff53a;
    this->state[4] = 0x510e527f;
    this->state[5] = 0x9b05688c;
    this->state[6] = 0x1f83d9ab;
    this->state[7] = 0x5be0cd19;
    std::memset(this->buffer, 0, sizeof(this->buffer));
    this->bufferSize = 0;
    this->totalBytes = 0;
    this->finished = false;
}

void Sha256::Transform(const u8 block[64])
{
    u32 words[64];
    for (size_t index = 0; index < 16; index++)
    {
        words[index] = LoadBigEndian(block + index * 4);
    }
    for (size_t index = 16; index < 64; index++)
    {
        const u32 previous15 = words[index - 15];
        const u32 previous2 = words[index - 2];
        const u32 sigma0 = RotateRight(previous15, 7) ^ RotateRight(previous15, 18) ^ (previous15 >> 3);
        const u32 sigma1 = RotateRight(previous2, 17) ^ RotateRight(previous2, 19) ^ (previous2 >> 10);
        words[index] = words[index - 16] + sigma0 + words[index - 7] + sigma1;
    }

    u32 a = this->state[0];
    u32 b = this->state[1];
    u32 c = this->state[2];
    u32 d = this->state[3];
    u32 e = this->state[4];
    u32 f = this->state[5];
    u32 g = this->state[6];
    u32 h = this->state[7];

    for (size_t index = 0; index < 64; index++)
    {
        const u32 sum1 = RotateRight(e, 6) ^ RotateRight(e, 11) ^ RotateRight(e, 25);
        const u32 choose = (e & f) ^ (~e & g);
        const u32 temporary1 = h + sum1 + choose + ROUND_CONSTANTS[index] + words[index];
        const u32 sum0 = RotateRight(a, 2) ^ RotateRight(a, 13) ^ RotateRight(a, 22);
        const u32 majority = (a & b) ^ (a & c) ^ (b & c);
        const u32 temporary2 = sum0 + majority;
        h = g;
        g = f;
        f = e;
        e = d + temporary1;
        d = c;
        c = b;
        b = a;
        a = temporary1 + temporary2;
    }

    this->state[0] += a;
    this->state[1] += b;
    this->state[2] += c;
    this->state[3] += d;
    this->state[4] += e;
    this->state[5] += f;
    this->state[6] += g;
    this->state[7] += h;
}

void Sha256::Update(const void *data, size_t size)
{
    if (this->finished || size == 0)
    {
        return;
    }
    const auto *bytes = static_cast<const u8 *>(data);
    this->totalBytes += size;

    while (size != 0)
    {
        const size_t available = sizeof(this->buffer) - this->bufferSize;
        const size_t copied = size < available ? size : available;
        std::memcpy(this->buffer + this->bufferSize, bytes, copied);
        this->bufferSize += copied;
        bytes += copied;
        size -= copied;
        if (this->bufferSize == sizeof(this->buffer))
        {
            this->Transform(this->buffer);
            this->bufferSize = 0;
        }
    }
}

Sha256Digest Sha256::Finish()
{
    if (!this->finished)
    {
        const u64 bitLength = this->totalBytes * 8;
        this->buffer[this->bufferSize++] = 0x80;
        if (this->bufferSize > 56)
        {
            std::memset(this->buffer + this->bufferSize, 0, sizeof(this->buffer) - this->bufferSize);
            this->Transform(this->buffer);
            this->bufferSize = 0;
        }
        std::memset(this->buffer + this->bufferSize, 0, 56 - this->bufferSize);
        for (size_t index = 0; index < 8; index++)
        {
            this->buffer[56 + index] = static_cast<u8>(bitLength >> (56 - index * 8));
        }
        this->Transform(this->buffer);
        this->bufferSize = 0;
        this->finished = true;
    }

    Sha256Digest digest{};
    for (size_t index = 0; index < 8; index++)
    {
        StoreBigEndian(digest.data() + index * 4, this->state[index]);
    }
    return digest;
}

Sha256Digest Sha256::Hash(const void *data, size_t size)
{
    Sha256 hash;
    hash.Update(data, size);
    return hash.Finish();
}

bool Sha256::SelfTest()
{
    static constexpr u8 EMPTY_DIGEST[32] = {
        0xe3, 0xb0, 0xc4, 0x42, 0x98, 0xfc, 0x1c, 0x14, 0x9a, 0xfb, 0xf4, 0xc8, 0x99, 0x6f, 0xb9, 0x24,
        0x27, 0xae, 0x41, 0xe4, 0x64, 0x9b, 0x93, 0x4c, 0xa4, 0x95, 0x99, 0x1b, 0x78, 0x52, 0xb8, 0x55,
    };
    static constexpr u8 ABC_DIGEST[32] = {
        0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea, 0x41, 0x41, 0x40, 0xde, 0x5d, 0xae, 0x22, 0x23,
        0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17, 0x7a, 0x9c, 0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad,
    };
    static constexpr u8 MILLION_A_DIGEST[32] = {
        0xcd, 0xc7, 0x6e, 0x5c, 0x99, 0x14, 0xfb, 0x92, 0x81, 0xa1, 0xc7, 0xe2, 0x84, 0xd7, 0x3e, 0x67,
        0xf1, 0x80, 0x9a, 0x48, 0xa4, 0x97, 0x20, 0x0e, 0x04, 0x6d, 0x39, 0xcc, 0xc7, 0x11, 0x2c, 0xd0,
    };

    const Sha256Digest empty = Sha256::Hash(NULL, 0);
    const char abc[] = "abc";
    const Sha256Digest oneShot = Sha256::Hash(abc, 3);
    Sha256 incremental;
    incremental.Update(abc, 1);
    incremental.Update(abc + 1, 2);
    const Sha256Digest chunked = incremental.Finish();

    u8 thousandAs[1000];
    std::memset(thousandAs, 'a', sizeof(thousandAs));
    Sha256 longInput;
    for (size_t index = 0; index < 1000; index++)
    {
        longInput.Update(thousandAs, sizeof(thousandAs));
    }
    const Sha256Digest millionAs = longInput.Finish();

    return DigestEquals(empty, EMPTY_DIGEST) && DigestEquals(oneShot, ABC_DIGEST) && oneShot == chunked &&
           DigestEquals(millionAs, MILLION_A_DIGEST);
}
