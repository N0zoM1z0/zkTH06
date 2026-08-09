#pragma once

#include "inttypes.hpp"

#include <array>
#include <cstddef>

using Sha256Digest = std::array<u8, 32>;

class Sha256
{
  public:
    Sha256();

    void Reset();
    void Update(const void *data, size_t size);
    Sha256Digest Finish();

    static Sha256Digest Hash(const void *data, size_t size);
    static bool SelfTest();

  private:
    void Transform(const u8 block[64]);

    u32 state[8] = {};
    u8 buffer[64] = {};
    size_t bufferSize = 0;
    u64 totalBytes = 0;
    bool finished = false;
};
