/*
 * Copyright (C) 2026 N0zoM1z0
 *
 * Differential counterexample search for the basic x87 profile used by TH06.
 * This compares result bits only.  It is evidence, not a correctness proof for
 * Berkeley SoftFloat, the inline assembly, or the future zkVM arithmetic.
 */

#include <errno.h>
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "platform.h"
#include "softfloat.h"

#if !defined(__i386__) && !defined(__x86_64__)
#error "the hardware side of this probe requires x87"
#endif

#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "this probe expects the little-endian SoftFloat extFloat80 layout"
#endif

_Static_assert(offsetof(extFloat80_t, signif) == 0,
               "extFloat80 significand must match the x87 memory layout");
_Static_assert(offsetof(extFloat80_t, signExp) == 8,
               "extFloat80 sign/exponent must match the x87 memory layout");

enum operation { OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_SQRT };

static const char *operation_name(enum operation op)
{
    static const char *const names[] = { "add", "sub", "mul", "div", "sqrt" };
    return names[op];
}

static extFloat80_t hardware(enum operation op, extFloat80_t a, extFloat80_t b)
{
    const uint16_t target = UINT16_C(0x027f);
    uint16_t old;
    extFloat80_t z;

    __asm__ volatile("fnstcw %0" : "=m"(old));
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(target));
    switch (op) {
    case OP_ADD:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfaddp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(z) : "m"(a), "m"(b) : "st");
        break;
    case OP_SUB:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfsubrp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(z) : "m"(a), "m"(b) : "st");
        break;
    case OP_MUL:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfmulp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(z) : "m"(a), "m"(b) : "st");
        break;
    case OP_DIV:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfdivrp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(z) : "m"(a), "m"(b) : "st");
        break;
    default:
        __asm__ volatile("fldt %1\n\tfsqrt\n\tfstpt %0"
                         : "=m"(z) : "m"(a) : "st");
        break;
    }
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(old));
    return z;
}

static extFloat80_t software(enum operation op, extFloat80_t a, extFloat80_t b)
{
    softfloat_roundingMode = softfloat_round_near_even;
    /* SoftFloat's value 64 means binary64-equivalent, 53-bit precision. */
    extF80_roundingPrecision = 64;
    softfloat_exceptionFlags = 0;
    switch (op) {
    case OP_ADD: return extF80_add(a, b);
    case OP_SUB: return extF80_sub(a, b);
    case OP_MUL: return extF80_mul(a, b);
    case OP_DIV: return extF80_div(a, b);
    default: return extF80_sqrt(a);
    }
}

static int equal(extFloat80_t a, extFloat80_t b)
{
    return a.signExp == b.signExp && a.signif == b.signif;
}

static uint32_t next32(uint32_t *state)
{
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static uint64_t next64(uint32_t *state)
{
    return ((uint64_t) next32(state) << 32) | next32(state);
}

static uint32_t finite_f32(uint32_t bits)
{
    if ((bits & UINT32_C(0x7f800000)) == UINT32_C(0x7f800000)) {
        bits ^= UINT32_C(0x00800000);
    }
    return bits;
}

/*
 * Generate only canonical finite extFloat80 values that could be held after a
 * 53-bit-precision x87 operation: explicit integer bit follows the exponent,
 * and the low eleven significand bits are zero.  One eighth of exponents are
 * drawn from boundary-heavy buckets; the rest cover the full finite range.
 */
static extFloat80_t finite_pc53_ext80(uint32_t *state)
{
    static const uint16_t edge_exponents[] = {
        0x0000, 0x0001, 0x0002, 0x0003,
        0x3ffd, 0x3ffe, 0x3fff, 0x4000, 0x4001,
        0x7ffc, 0x7ffd, 0x7ffe
    };
    uint32_t selector = next32(state);
    uint16_t exponent;
    extFloat80_t value;

    if ((selector & 7) == 0) {
        size_t index = (selector >> 3)
                     % (sizeof edge_exponents / sizeof edge_exponents[0]);
        exponent = edge_exponents[index];
    } else {
        exponent = (uint16_t) (selector & UINT32_C(0x7fff));
        if (exponent == UINT16_C(0x7fff)) exponent = UINT16_C(0x7ffe);
    }

    value.signif = next64(state) & UINT64_C(0x7ffffffffffff800);
    if (exponent != 0) value.signif |= UINT64_C(0x8000000000000000);
    value.signExp = exponent;
    if (next32(state) & 1) value.signExp |= UINT16_C(0x8000);
    return value;
}

static int check_ext80(enum operation op, extFloat80_t a, extFloat80_t b,
                       const char *input_class)
{
    extFloat80_t h;
    extFloat80_t s;

    if (op == OP_SQRT) a.signExp &= UINT16_C(0x7fff);
    h = hardware(op, a, b);
    s = software(op, a, b);
    if (!equal(h, s)) {
        fprintf(stderr,
                "mismatch class=%s op=%s"
                " a=%04" PRIx16 ":%016" PRIx64
                " b=%04" PRIx16 ":%016" PRIx64
                " hw=%04" PRIx16 ":%016" PRIx64
                " sf=%04" PRIx16 ":%016" PRIx64 " flags=%02x\n",
                input_class, operation_name(op),
                a.signExp, a.signif, b.signExp, b.signif,
                h.signExp, h.signif, s.signExp, s.signif,
                (unsigned) softfloat_exceptionFlags);
        return 0;
    }
    return 1;
}

static int check_f32(enum operation op, uint32_t a_bits, uint32_t b_bits)
{
    float32_t af = { a_bits };
    float32_t bf = { b_bits };
    extFloat80_t a;
    extFloat80_t b;

    if (op == OP_SQRT) af.v &= UINT32_C(0x7fffffff);
    a = f32_to_extF80(af);
    b = f32_to_extF80(bf);
    return check_ext80(op, a, b, "f32");
}

static uint64_t parse_cases(const char *text, const char *name)
{
    char *end;
    unsigned long long value;

    errno = 0;
    value = strtoull(text, &end, 0);
    if (errno || *text == '\0' || *text == '-' || *end != '\0') {
        fprintf(stderr, "invalid %s case count: %s\n", name, text);
        exit(2);
    }
    return (uint64_t) value;
}

int main(int argc, char **argv)
{
    uint32_t state = UINT32_C(0x5a17c9e3);
    uint64_t f32_cases = argc > 1 ? parse_cases(argv[1], "f32") : 100000;
    uint64_t ext80_cases = argc > 2 ? parse_cases(argv[2], "ext80") : f32_cases;
    static const uint32_t fixed_f32[] = {
        0x00000000, 0x80000000, 0x00000001, 0x007fffff,
        0x00800000, 0x3f000000, 0x3f7fffff, 0x3f800000,
        0x3f800001, 0x40000000, 0x7f000000, 0x7f7fffff,
        0x80800000, 0xff7fffff
    };
    static const extFloat80_t fixed_ext80[] = {
        { .signif = 0x0000000000000000, .signExp = 0x0000 },
        { .signif = 0x0000000000000000, .signExp = 0x8000 },
        { .signif = 0x0000000000000800, .signExp = 0x0000 },
        { .signif = 0x7ffffffffffff800, .signExp = 0x0000 },
        { .signif = 0x8000000000000000, .signExp = 0x0001 },
        { .signif = 0x8000000000000800, .signExp = 0x0001 },
        { .signif = 0xfffffffffffff800, .signExp = 0x3ffe },
        { .signif = 0x8000000000000000, .signExp = 0x3ffe },
        { .signif = 0x8000000000000000, .signExp = 0x3fff },
        { .signif = 0x8000000000000800, .signExp = 0x3fff },
        { .signif = 0xfffffffffffff800, .signExp = 0x3fff },
        { .signif = 0x8000000000000000, .signExp = 0x4000 },
        { .signif = 0xfffffffffffff800, .signExp = 0x7ffe },
        { .signif = 0x8000000000000000, .signExp = 0xbffe },
        { .signif = 0x8000000000000000, .signExp = 0xbfff },
        { .signif = 0x8000000000000800, .signExp = 0xbfff },
        { .signif = 0xfffffffffffff800, .signExp = 0xbfff },
        { .signif = 0xfffffffffffff800, .signExp = 0xfffe }
    };
    uint64_t checked_f32 = 0;
    uint64_t checked_ext80 = 0;

    if (argc > 3) {
        fprintf(stderr, "usage: %s [f32-cases [ext80-cases]]\n", argv[0]);
        return 2;
    }

    for (unsigned raw_op = OP_ADD; raw_op <= OP_SQRT; ++raw_op) {
        enum operation op = (enum operation) raw_op;
        size_t f32_b_count = op == OP_SQRT
                           ? 1 : sizeof fixed_f32 / sizeof fixed_f32[0];
        size_t ext_b_count = op == OP_SQRT
                           ? 1 : sizeof fixed_ext80 / sizeof fixed_ext80[0];

        for (size_t i = 0; i < sizeof fixed_f32 / sizeof fixed_f32[0]; ++i) {
            for (size_t j = 0; j < f32_b_count; ++j) {
                if (!check_f32(op, fixed_f32[i], fixed_f32[j])) return 1;
                ++checked_f32;
            }
        }
        for (uint64_t i = 0; i < f32_cases; ++i) {
            uint32_t a = finite_f32(next32(&state));
            uint32_t b = finite_f32(next32(&state));
            if (!check_f32(op, a, b)) return 1;
            ++checked_f32;
        }

        for (size_t i = 0; i < sizeof fixed_ext80 / sizeof fixed_ext80[0]; ++i) {
            for (size_t j = 0; j < ext_b_count; ++j) {
                if (!check_ext80(op, fixed_ext80[i], fixed_ext80[j], "ext80")) {
                    return 1;
                }
                ++checked_ext80;
            }
        }
        for (uint64_t i = 0; i < ext80_cases; ++i) {
            extFloat80_t a = finite_pc53_ext80(&state);
            extFloat80_t b = finite_pc53_ext80(&state);
            if (!check_ext80(op, a, b, "ext80")) return 1;
            ++checked_ext80;
        }
    }

    printf("matched %" PRIu64 " f32-derived and %" PRIu64
           " canonical PC53 ext80 basic-operation results at x87 CW 0x027f\n",
           checked_f32, checked_ext80);
    return 0;
}
