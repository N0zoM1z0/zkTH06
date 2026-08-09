/*
 * Copyright (C) 2026 N0zoM1z0
 *
 * Differential counterexample search for the x87 profile used by TH06.  It
 * compares result bits and the six x87 exception-status bits across finite
 * basic arithmetic, stores, rounding, and integer conversion.  It also checks
 * condition codes for the memory-operand comparisons that drive TH06 branches,
 * including fixed canonical NaNs.  This is evidence, not a correctness proof
 * for Berkeley SoftFloat, this harness, or future zkVM arithmetic.
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
enum boundary_operation {
    BOUNDARY_STORE_F32,
    BOUNDARY_STORE_F64,
    BOUNDARY_FRNDINT,
    BOUNDARY_FIST_I32,
    BOUNDARY_FIST_I64
};
enum comparison_width { COMPARE_F32, COMPARE_F64 };
enum comparison_relation {
    REL_GREATER,
    REL_LESS,
    REL_EQUAL,
    REL_UNORDERED,
    RELATION_COUNT
};

#define X87_EXCEPTION_MASK UINT16_C(0x003f)
#define X87_CONDITION_MASK UINT16_C(0x4700)
#define X87_CONDITION_GREATER UINT16_C(0x0000)
#define X87_CONDITION_LESS UINT16_C(0x0100)
#define X87_CONDITION_EQUAL UINT16_C(0x4000)
#define X87_CONDITION_UNORDERED UINT16_C(0x4500)

struct hardware_result {
    extFloat80_t value;
    uint16_t status;
};

struct boundary_result {
    extFloat80_t value;
    uint64_t scalar;
    uint16_t status;
};

struct rounding_profile {
    const char *name;
    uint16_t control_word;
    uint_fast8_t softfloat_mode;
};

static uint16_t softfloat_x87_exception_bits(uint_fast8_t flags);
static uint64_t basic_exception_counts[6];
static uint64_t boundary_exception_counts[6];
static uint64_t comparison_exception_counts[6];
static uint64_t comparison_relation_counts[RELATION_COUNT];

static void record_exception_bits(uint64_t counts[6], uint16_t status)
{
    for (unsigned bit = 0; bit < 6; ++bit) {
        if (status & (UINT16_C(1) << bit)) ++counts[bit];
    }
}

static void print_exception_counts(const char *label, const uint64_t counts[6])
{
    printf("%s exception observations: invalid=%" PRIu64
           " denormal=%" PRIu64 " divide-by-zero=%" PRIu64
           " overflow=%" PRIu64 " underflow=%" PRIu64
           " inexact=%" PRIu64 "\n",
           label, counts[0], counts[1], counts[2], counts[3], counts[4],
           counts[5]);
}

static const char *operation_name(enum operation op)
{
    static const char *const names[] = { "add", "sub", "mul", "div", "sqrt" };
    return names[op];
}

static const char *boundary_name(enum boundary_operation op)
{
    static const char *const names[] = {
        "store-f32", "store-f64", "frndint", "fist-i32", "fist-i64"
    };
    return names[op];
}

static const char *comparison_width_name(enum comparison_width width)
{
    return width == COMPARE_F32 ? "f32" : "f64";
}

static struct hardware_result
hardware(enum operation op, extFloat80_t a, extFloat80_t b)
{
    const uint16_t target = UINT16_C(0x027f);
    uint16_t old;
    struct hardware_result result;

    __asm__ volatile("fnstcw %0" : "=m"(old));
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(target));
    switch (op) {
    case OP_ADD:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfaddp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(result.value) : "m"(a), "m"(b) : "st");
        break;
    case OP_SUB:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfsubrp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(result.value) : "m"(a), "m"(b) : "st");
        break;
    case OP_MUL:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfmulp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(result.value) : "m"(a), "m"(b) : "st");
        break;
    case OP_DIV:
        __asm__ volatile(
            "fldt %1\n\tfldt %2\n\tfdivrp %%st, %%st(1)\n\tfstpt %0"
            : "=m"(result.value) : "m"(a), "m"(b) : "st");
        break;
    default:
        __asm__ volatile("fldt %1\n\tfsqrt\n\tfstpt %0"
                         : "=m"(result.value) : "m"(a) : "st");
        break;
    }
    __asm__ volatile("fnstsw %0" : "=m"(result.status));
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(old));
    return result;
}

static extFloat80_t software(enum operation op, extFloat80_t a, extFloat80_t b)
{
    softfloat_roundingMode = softfloat_round_near_even;
    softfloat_detectTininess = softfloat_tininess_afterRounding;
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

static struct boundary_result
hardware_boundary(enum boundary_operation op, extFloat80_t a,
                  uint16_t control_word)
{
    uint16_t old;
    struct boundary_result result = { 0 };

    __asm__ volatile("fnstcw %0" : "=m"(old));
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(control_word));
    switch (op) {
    case BOUNDARY_STORE_F32: {
        uint32_t value;
        __asm__ volatile("fldt %1\n\tfstps %0"
                         : "=m"(value) : "m"(a) : "st");
        result.scalar = value;
        break;
    }
    case BOUNDARY_STORE_F64: {
        uint64_t value;
        __asm__ volatile("fldt %1\n\tfstpl %0"
                         : "=m"(value) : "m"(a) : "st");
        result.scalar = value;
        break;
    }
    case BOUNDARY_FRNDINT:
        __asm__ volatile("fldt %1\n\tfrndint\n\tfstpt %0"
                         : "=m"(result.value) : "m"(a) : "st");
        break;
    case BOUNDARY_FIST_I32: {
        int32_t value;
        __asm__ volatile("fldt %1\n\tfistpl %0"
                         : "=m"(value) : "m"(a) : "st");
        result.scalar = (uint32_t) value;
        break;
    }
    default: {
        int64_t value;
        __asm__ volatile("fldt %1\n\tfistpll %0"
                         : "=m"(value) : "m"(a) : "st");
        result.scalar = (uint64_t) value;
        break;
    }
    }
    __asm__ volatile("fnstsw %0" : "=m"(result.status));
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(old));
    return result;
}

static struct boundary_result
software_boundary(enum boundary_operation op, extFloat80_t a,
                  uint_fast8_t rounding_mode)
{
    struct boundary_result result = { 0 };

    softfloat_roundingMode = rounding_mode;
    softfloat_detectTininess = softfloat_tininess_afterRounding;
    extF80_roundingPrecision = 64;
    softfloat_exceptionFlags = 0;
    switch (op) {
    case BOUNDARY_STORE_F32:
        result.scalar = extF80_to_f32(a).v;
        break;
    case BOUNDARY_STORE_F64:
        result.scalar = extF80_to_f64(a).v;
        break;
    case BOUNDARY_FRNDINT:
        result.value = extF80_roundToInt(a, rounding_mode, true);
        break;
    case BOUNDARY_FIST_I32:
        result.scalar = (uint32_t) (int32_t)
            extF80_to_i32(a, rounding_mode, true);
        break;
    default:
        result.scalar = (uint64_t) (int64_t)
            extF80_to_i64(a, rounding_mode, true);
        break;
    }
    result.status = softfloat_x87_exception_bits(softfloat_exceptionFlags);
    return result;
}

static uint16_t
hardware_compare(enum comparison_width width, extFloat80_t a, uint64_t b_bits)
{
    const uint16_t target = UINT16_C(0x027f);
    uint16_t old;
    uint16_t status;

    __asm__ volatile("fnstcw %0" : "=m"(old));
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(target));
    if (width == COMPARE_F32) {
        uint32_t operand = (uint32_t) b_bits;
        __asm__ volatile("fldt %1\n\tfcomps %2\n\tfnstsw %0"
                         : "=m"(status) : "m"(a), "m"(operand) : "st");
    } else {
        __asm__ volatile("fldt %1\n\tfcompl %2\n\tfnstsw %0"
                         : "=m"(status) : "m"(a), "m"(b_bits) : "st");
    }
    __asm__ volatile("fnclex\n\tfldcw %0" : : "m"(old));
    return status;
}

static uint16_t
software_compare(extFloat80_t a, extFloat80_t b,
                 enum comparison_relation *relation)
{
    uint16_t condition;

    softfloat_exceptionFlags = 0;
    if (extF80_eq_signaling(a, b)) {
        *relation = REL_EQUAL;
        condition = X87_CONDITION_EQUAL;
    } else if (softfloat_exceptionFlags & softfloat_flag_invalid) {
        *relation = REL_UNORDERED;
        condition = X87_CONDITION_UNORDERED;
    } else if (extF80_lt(a, b)) {
        *relation = REL_LESS;
        condition = X87_CONDITION_LESS;
    } else {
        *relation = REL_GREATER;
        condition = X87_CONDITION_GREATER;
    }
    return condition | softfloat_x87_exception_bits(softfloat_exceptionFlags);
}

static int equal(extFloat80_t a, extFloat80_t b)
{
    return a.signExp == b.signExp && a.signif == b.signif;
}

/* SoftFloat has five IEEE flags; x87 denormal-operand bit 1 is derived below. */
static uint16_t softfloat_x87_exception_bits(uint_fast8_t flags)
{
    uint16_t bits = 0;
    if (flags & softfloat_flag_invalid) bits |= UINT16_C(1) << 0;
    if (flags & softfloat_flag_infinite) bits |= UINT16_C(1) << 2;
    if (flags & softfloat_flag_overflow) bits |= UINT16_C(1) << 3;
    if (flags & softfloat_flag_underflow) bits |= UINT16_C(1) << 4;
    if (flags & softfloat_flag_inexact) bits |= UINT16_C(1) << 5;
    return bits;
}

static int is_subnormal_ext80(extFloat80_t value)
{
    return (value.signExp & UINT16_C(0x7fff)) == 0 && value.signif != 0;
}

static int is_zero_ext80(extFloat80_t value)
{
    return (value.signExp & UINT16_C(0x7fff)) == 0 && value.signif == 0;
}

static int is_subnormal_f32(uint32_t bits)
{
    return (bits & UINT32_C(0x7f800000)) == 0
        && (bits & UINT32_C(0x007fffff)) != 0;
}

static int is_subnormal_f64(uint64_t bits)
{
    return (bits & UINT64_C(0x7ff0000000000000)) == 0
        && (bits & UINT64_C(0x000fffffffffffff)) != 0;
}

static int check_compare(extFloat80_t a, enum comparison_width width,
                         uint64_t b_bits, const char *input_class)
{
    extFloat80_t b;
    enum comparison_relation relation;
    uint16_t hardware_status = hardware_compare(width, a, b_bits);
    uint16_t expected_status;

    if (width == COMPARE_F32) {
        float32_t source = { (uint32_t) b_bits };
        b = f32_to_extF80(source);
    } else {
        float64_t source = { b_bits };
        b = f64_to_extF80(source);
    }
    expected_status = software_compare(a, b, &relation);

    /* FCOM's invalid result takes priority over denormal-operand signaling. */
    if (!(expected_status & (UINT16_C(1) << 0))
        && (is_subnormal_ext80(a)
            || (width == COMPARE_F32
                    ? is_subnormal_f32((uint32_t) b_bits)
                    : is_subnormal_f64(b_bits)))) {
        expected_status |= UINT16_C(1) << 1;
    }

    if ((hardware_status & (X87_EXCEPTION_MASK | X87_CONDITION_MASK))
        != expected_status) {
        fprintf(stderr,
                "mismatch class=%s comparison=%s"
                " a=%04" PRIx16 ":%016" PRIx64
                " b_bits=%016" PRIx64
                " x87_status=%04" PRIx16 " expected=%04" PRIx16
                " sf_flags=%02x\n",
                input_class, comparison_width_name(width),
                a.signExp, a.signif, b_bits, hardware_status,
                expected_status, (unsigned) softfloat_exceptionFlags);
        return 0;
    }
    record_exception_bits(comparison_exception_counts, hardware_status);
    ++comparison_relation_counts[relation];
    return 1;
}

static int check_boundary(enum boundary_operation op, extFloat80_t a,
                          const char *input_class,
                          const struct rounding_profile *profile)
{
    struct boundary_result h = hardware_boundary(op, a, profile->control_word);
    struct boundary_result s = software_boundary(op, a, profile->softfloat_mode);
    uint16_t expected_status = s.status;
    int same_value;

    /* FSTP and FISTP do not signal #D; FRNDINT does for a subnormal source. */
    if (op == BOUNDARY_FRNDINT && is_subnormal_ext80(a)) {
        expected_status |= UINT16_C(1) << 1;
    }

    same_value = op == BOUNDARY_FRNDINT
               ? equal(h.value, s.value) : h.scalar == s.scalar;
    if (!same_value || (h.status & UINT16_C(0x003f)) != expected_status) {
        fprintf(stderr,
                "mismatch class=%s boundary=%s rounding=%s"
                " a=%04" PRIx16 ":%016" PRIx64
                " hw_ext=%04" PRIx16 ":%016" PRIx64
                " sf_ext=%04" PRIx16 ":%016" PRIx64
                " hw_scalar=%016" PRIx64 " sf_scalar=%016" PRIx64
                " x87_status=%04" PRIx16 " sf_flags=%02x expected=%02" PRIx16 "\n",
                input_class, boundary_name(op), profile->name,
                a.signExp, a.signif,
                h.value.signExp, h.value.signif,
                s.value.signExp, s.value.signif,
                h.scalar, s.scalar, h.status,
                (unsigned) softfloat_exceptionFlags, expected_status);
        return 0;
    }
    record_exception_bits(boundary_exception_counts, h.status);
    return 1;
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

static uint64_t finite_f64(uint64_t bits)
{
    if ((bits & UINT64_C(0x7ff0000000000000))
        == UINT64_C(0x7ff0000000000000)) {
        bits ^= UINT64_C(0x0010000000000000);
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
    struct hardware_result h;
    extFloat80_t s;
    uint16_t expected_status;

    h = hardware(op, a, b);
    s = software(op, a, b);
    expected_status = softfloat_x87_exception_bits(softfloat_exceptionFlags);
    /* Invalid sqrt and zero-divide take priority over #D for these forms. */
    if ((op == OP_SQRT
         && !(a.signExp & UINT16_C(0x8000))
         && is_subnormal_ext80(a))
        || (op != OP_SQRT
            && (is_subnormal_ext80(a) || is_subnormal_ext80(b))
            && !(op == OP_DIV && is_zero_ext80(b)))) {
        expected_status |= UINT16_C(1) << 1;
    }
    if (!equal(h.value, s)
        || (h.status & UINT16_C(0x003f)) != expected_status) {
        fprintf(stderr,
                "mismatch class=%s op=%s"
                " a=%04" PRIx16 ":%016" PRIx64
                " b=%04" PRIx16 ":%016" PRIx64
                " hw=%04" PRIx16 ":%016" PRIx64
                " sf=%04" PRIx16 ":%016" PRIx64
                " x87_status=%04" PRIx16 " sf_flags=%02x expected=%02" PRIx16 "\n",
                input_class, operation_name(op),
                a.signExp, a.signif, b.signExp, b.signif,
                h.value.signExp, h.value.signif, s.signExp, s.signif,
                h.status, (unsigned) softfloat_exceptionFlags, expected_status);
        return 0;
    }
    record_exception_bits(basic_exception_counts, h.status);
    return 1;
}

static int check_f32(enum operation op, uint32_t a_bits, uint32_t b_bits)
{
    float32_t af = { a_bits };
    float32_t bf = { b_bits };
    extFloat80_t a;
    extFloat80_t b;

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
    static const extFloat80_t fixed_conversion[] = {
        { .signif = 0xc000000000000000, .signExp = 0x3fff },
        { .signif = 0xa000000000000000, .signExp = 0x4000 },
        { .signif = 0xc000000000000000, .signExp = 0xbfff },
        { .signif = 0xa000000000000000, .signExp = 0xc000 },
        { .signif = 0xfffffffe00000000, .signExp = 0x401d },
        { .signif = 0xffffffff00000000, .signExp = 0x401d },
        { .signif = 0x8000000000000000, .signExp = 0x401e },
        { .signif = 0x8000000080000000, .signExp = 0x401e },
        { .signif = 0x8000000000000000, .signExp = 0xc01e },
        { .signif = 0x8000000080000000, .signExp = 0xc01e },
        { .signif = 0xfffffffffffff800, .signExp = 0x403d },
        { .signif = 0x8000000000000000, .signExp = 0x403e },
        { .signif = 0x8000000000000800, .signExp = 0x403e },
        { .signif = 0x8000000000000000, .signExp = 0xc03e },
        { .signif = 0x8000000000000800, .signExp = 0xc03e }
    };
    static const uint32_t fixed_compare_f32[] = {
        0x00000000, 0x80000000, 0x00000001, 0x007fffff,
        0x00800000, 0x3f800000, 0xbf800000, 0x7f800000,
        0xff800000, 0x7fc00001, 0x7f800001
    };
    static const uint64_t fixed_compare_f64[] = {
        UINT64_C(0x0000000000000000), UINT64_C(0x8000000000000000),
        UINT64_C(0x0000000000000001), UINT64_C(0x000fffffffffffff),
        UINT64_C(0x0010000000000000), UINT64_C(0x3ff0000000000000),
        UINT64_C(0xbff0000000000000), UINT64_C(0x7ff0000000000000),
        UINT64_C(0xfff0000000000000), UINT64_C(0x7ff8000000000001),
        UINT64_C(0x7ff0000000000001)
    };
    static const extFloat80_t fixed_compare_ext80[] = {
        { .signif = 0x0000000000000000, .signExp = 0x0000 },
        { .signif = 0x0000000000000000, .signExp = 0x8000 },
        { .signif = 0x0000000000000800, .signExp = 0x0000 },
        { .signif = 0x7ffffffffffff800, .signExp = 0x0000 },
        { .signif = 0x8000000000000000, .signExp = 0x3fff },
        { .signif = 0x8000000000000000, .signExp = 0xbfff },
        { .signif = 0x8000000000000000, .signExp = 0x7fff },
        { .signif = 0x8000000000000000, .signExp = 0xffff },
        { .signif = 0xc000000000000001, .signExp = 0x7fff },
        { .signif = 0x8000000000000001, .signExp = 0x7fff }
    };
    static const struct rounding_profile profiles[] = {
        { "nearest-even", UINT16_C(0x027f), softfloat_round_near_even },
        { "toward-zero", UINT16_C(0x0e7f), softfloat_round_minMag }
    };
    uint64_t checked_f32 = 0;
    uint64_t checked_ext80 = 0;
    uint64_t checked_boundary_f32 = 0;
    uint64_t checked_boundary_ext80 = 0;
    uint64_t checked_compare_f32 = 0;
    uint64_t checked_compare_f64 = 0;

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
           " canonical PC53 ext80 basic-operation result/status tuples"
           " at x87 CW 0x027f\n",
           checked_f32, checked_ext80);
    print_exception_counts("basic", basic_exception_counts);

    for (size_t p = 0; p < sizeof profiles / sizeof profiles[0]; ++p) {
        for (unsigned raw_op = BOUNDARY_STORE_F32;
             raw_op <= BOUNDARY_FIST_I64; ++raw_op) {
            enum boundary_operation op = (enum boundary_operation) raw_op;

            for (size_t i = 0; i < sizeof fixed_f32 / sizeof fixed_f32[0]; ++i) {
                float32_t input = { fixed_f32[i] };
                if (!check_boundary(op, f32_to_extF80(input), "f32", &profiles[p])) {
                    return 1;
                }
                ++checked_boundary_f32;
            }
            for (uint64_t i = 0; i < f32_cases; ++i) {
                float32_t input = { finite_f32(next32(&state)) };
                if (!check_boundary(op, f32_to_extF80(input), "f32", &profiles[p])) {
                    return 1;
                }
                ++checked_boundary_f32;
            }

            for (size_t i = 0; i < sizeof fixed_ext80 / sizeof fixed_ext80[0]; ++i) {
                if (!check_boundary(op, fixed_ext80[i], "ext80", &profiles[p])) {
                    return 1;
                }
                ++checked_boundary_ext80;
            }
            for (size_t i = 0;
                 i < sizeof fixed_conversion / sizeof fixed_conversion[0]; ++i) {
                if (!check_boundary(op, fixed_conversion[i], "ext80", &profiles[p])) {
                    return 1;
                }
                ++checked_boundary_ext80;
            }
            for (uint64_t i = 0; i < ext80_cases; ++i) {
                extFloat80_t input = finite_pc53_ext80(&state);
                if (!check_boundary(op, input, "ext80", &profiles[p])) return 1;
                ++checked_boundary_ext80;
            }
        }
    }

    printf("matched %" PRIu64 " f32-derived and %" PRIu64
           " canonical PC53 ext80 store/round/conversion result/status tuples"
           " across nearest-even and toward-zero\n",
           checked_boundary_f32, checked_boundary_ext80);
    print_exception_counts("boundary", boundary_exception_counts);

    for (size_t i = 0;
         i < sizeof fixed_compare_ext80 / sizeof fixed_compare_ext80[0]; ++i) {
        for (size_t j = 0;
             j < sizeof fixed_compare_f32 / sizeof fixed_compare_f32[0]; ++j) {
            if (!check_compare(fixed_compare_ext80[i], COMPARE_F32,
                               fixed_compare_f32[j], "fixed-ext80")) return 1;
            ++checked_compare_f32;
        }
        for (size_t j = 0;
             j < sizeof fixed_compare_f64 / sizeof fixed_compare_f64[0]; ++j) {
            if (!check_compare(fixed_compare_ext80[i], COMPARE_F64,
                               fixed_compare_f64[j], "fixed-ext80")) return 1;
            ++checked_compare_f64;
        }
    }
    for (uint64_t i = 0; i < f32_cases; ++i) {
        float32_t a = { finite_f32(next32(&state)) };
        uint32_t b = finite_f32(next32(&state));
        if (!check_compare(f32_to_extF80(a), COMPARE_F32, b, "f32")) return 1;
        ++checked_compare_f32;
    }
    for (uint64_t i = 0; i < ext80_cases; ++i) {
        extFloat80_t a = finite_pc53_ext80(&state);
        uint32_t b = finite_f32(next32(&state));
        if (!check_compare(a, COMPARE_F32, b, "ext80")) return 1;
        ++checked_compare_f32;
    }
    for (uint64_t i = 0; i < f32_cases; ++i) {
        float64_t a = { finite_f64(next64(&state)) };
        uint64_t b = finite_f64(next64(&state));
        if (!check_compare(f64_to_extF80(a), COMPARE_F64, b, "f64")) return 1;
        ++checked_compare_f64;
    }
    for (uint64_t i = 0; i < ext80_cases; ++i) {
        extFloat80_t a = finite_pc53_ext80(&state);
        uint64_t b = finite_f64(next64(&state));
        if (!check_compare(a, COMPARE_F64, b, "ext80")) return 1;
        ++checked_compare_f64;
    }

    printf("matched %" PRIu64 " fcomp-m32 and %" PRIu64
           " fcomp-m64 condition/status tuples at x87 CW 0x027f\n",
           checked_compare_f32, checked_compare_f64);
    printf("comparison relations: greater=%" PRIu64 " less=%" PRIu64
           " equal=%" PRIu64 " unordered=%" PRIu64 "\n",
           comparison_relation_counts[REL_GREATER],
           comparison_relation_counts[REL_LESS],
           comparison_relation_counts[REL_EQUAL],
           comparison_relation_counts[REL_UNORDERED]);
    print_exception_counts("comparison", comparison_exception_counts);
    return 0;
}
