use km003c_lib::{KM003C, DeviceSelector, auth, firmware::{FirmwareImage, FirmwareUsbMode, PreparedFirmwareUpdate, find_firmware_device}};
use std::{fs, path::Path, time::Duration};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
async fn mode(expected: FirmwareUsbMode, selector: &DeviceSelector) -> Result<()> {
    for _ in 0..80 {
        if let Ok(found) = find_firmware_device(selector).await {
            if found.mode == expected { return Ok(()); }
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    Err(format!("did not enter {expected:?}").into())
}
async fn read_dfu(d: &mut KM003C, addr: u32, size: u32) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    while out.len() < size as usize {
        let count = (size as usize-out.len()).min(4096) as u32;
        let address = addr+out.len() as u32;
        d.send_raw(&auth::build_memory_read_packet(address, count, 1)).await?;
        let confirmation = d.receive_raw().await?;
        if confirmation.len()!=20 || confirmation[0]&0x7f != 0x44 || auth::parse_memory_read_confirmation(&confirmation[4..]) != Some((address,count)) {
            return Err(format!("bad memory confirmation at {address:x}: {confirmation:02x?}").into());
        }
        let mut encrypted = Vec::new();
        let aligned = count.div_ceil(16)*16;
        while encrypted.len() < aligned as usize { encrypted.extend(d.receive_raw().await?); }
        if encrypted.len()!=aligned as usize {return Err("unexpected memory transfer length".into());}
        let plaintext = auth::aes_ecb_decrypt_blocks(&encrypted, &auth::MEMORY_READ_KEY)?;
        out.extend(&plaintext[..count as usize]);
    }
    Ok(out)
}
#[tokio::main]
async fn main() -> Result<()> {
    let root = Path::new("/home/okhsunrog/tmp_zfs/codex_tmp/km003c-rust-bringup");
    assert_eq!(std::env::args().nth(1).as_deref(), Some("--run-smoke"));
    let image = FirmwareImage::parse(&fs::read(root.join("rust-smoke.mencrypt"))?)?;
    let rollback = FirmwareImage::parse(&fs::read("/home/okhsunrog/tmp_zfs/codex_tmp/km003c-flash-cycle-2026-10-28/original-1.9.9-exact.mencrypt")?)?;
    image.validate_for_update()?;
    rollback.validate_for_update()?;
    let initial = find_firmware_device(&DeviceSelector::First).await?;
    assert_eq!(initial.mode, FirmwareUsbMode::Application);
    let selector = initial.port_selector.ok_or("no stable port identity")?;
    let prepared = PreparedFirmwareUpdate::prepare(image.clone(), selector.clone(), |_| {}).await?;
    let backup = prepared.backup().ok_or("missing app backup")?;
    assert_eq!(backup.data(), rollback.installed_data()?);
    let mut saved = fs::File::create(root.join("verified-original-app.bin"))?;
    use std::io::Write;
    saved.write_all(backup.data())?; saved.sync_all()?;
    drop(prepared);
    println!("Two matching backup reads saved; exact rollback package verified");
    let mut app = KM003C::open_maintenance(selector.clone()).await?;
    app.jump_to_dfu().await?; drop(app);
    mode(FirmwareUsbMode::Dfu, &selector).await?;
    let mut d = KM003C::open_maintenance(selector.clone()).await?;
    let info = d.get_bootloader_info().await?;
    assert_eq!(info.model,"KM003C"); assert_eq!(info.hw_version,"2.1");
    let boot_before = read_dfu(&mut d,4,0x3ffc).await?;
    fs::write(root.join("boot-before.bin"), &boot_before)?;
    let known = fs::read("/home/okhsunrog/code/km003c-protocol-research/fw/bootloader_hw2.1_00000004-00003fff.bin")?;
    assert_eq!(boot_before, known);
    let marker_before = read_dfu(&mut d,0x200f0fc0,16).await?;
    fs::write(root.join("marker-before.bin"),marker_before)?;
    d.update_firmware(&image, |p| println!("{p:?}")).await?;
    let installed = read_dfu(&mut d,0x4000,image.data().len() as u32).await?;
    assert_eq!(installed,image.installed_data()?);
    fs::write(root.join("smoke-readback.bin"),installed)?;
    assert_eq!(read_dfu(&mut d,4,0x3ffc).await?,boot_before);
    println!("Custom image readback and unchanged bootloader verified; starting Rust");
    d.jump_to_application().await?; drop(d);
    // Require re-enumeration to avoid mistaking the old DFU handle for Rust's return.
    tokio::time::sleep(Duration::from_secs(3)).await;
    mode(FirmwareUsbMode::Dfu, &selector).await?;
    let mut d = KM003C::open_maintenance(selector).await?;
    d.get_bootloader_info().await?;
    let marker = read_dfu(&mut d,0x200f0fc0,16).await?;
    fs::write(root.join("marker-after.bin"),&marker)?;
    let words:Vec<_> = marker.chunks_exact(4).map(|c|u32::from_le_bytes(c.try_into().unwrap())).collect();
    println!("Rust result: {words:08x?}");
    assert_eq!(words, [0x52555354,1,0x4000,0x600d0001]);
    assert_eq!(read_dfu(&mut d,4,0x3ffc).await?,boot_before);
    println!("PASS: Rust main completed and reset into the original bootloader");
    Ok(())
}
