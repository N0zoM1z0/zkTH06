#![forbid(unsafe_code)]

use std::{env, error::Error, io};

use openvm_sdk::{fs::read_object_from_file, openvm_circuit::arch::ContinuationVmProof, SC};
use p3_field::PrimeField32;

fn parse_digest(value: &str) -> Result<[u8; 32], Box<dyn Error>> {
    let value = value.strip_prefix("0x").unwrap_or(value);
    if value.len() != 64 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "expected digest must contain exactly 64 hex digits",
        )
        .into());
    }
    let mut digest = [0u8; 32];
    for (index, byte) in digest.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16)?;
    }
    Ok(digest)
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut arguments = env::args();
    let program = arguments.next().unwrap_or_default();
    let proof_path = arguments.next().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("usage: {program} APP_PROOF EXPECTED_SHA256"),
        )
    })?;
    let expected = parse_digest(&arguments.next().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("usage: {program} APP_PROOF EXPECTED_SHA256"),
        )
    })?)?;
    if arguments.next().is_some() {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "too many arguments").into());
    }

    let proof: ContinuationVmProof<SC> = read_object_from_file(proof_path)?;
    let public_values = &proof.user_public_values.public_values;
    if public_values.len() != expected.len() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            format!(
                "expected 32 public bytes, proof contains {}",
                public_values.len()
            ),
        )
        .into());
    }
    let mut actual = [0u8; 32];
    for (output, value) in actual.iter_mut().zip(public_values) {
        *output = u8::try_from(value.as_canonical_u32()).map_err(|_| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "proof public value is not a byte",
            )
        })?;
    }
    let actual_hex = actual
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    if actual != expected {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            format!("public digest mismatch: actual {actual_hex}"),
        )
        .into());
    }
    println!("proof public digest matches: {actual_hex}");
    Ok(())
}
