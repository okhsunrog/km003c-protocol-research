use clap::Parser;
use polars::prelude::*;
use polars_utils::plpath::PlPath;
use rtshark::{Packet as RtSharkPacket, RTSharkBuilder};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Parser, Debug)]
#[command(author, version, about = "Convert pcap files to Parquet format with USB payload data")]
struct Cli {
    /// Input pcapng file to process
    #[arg(short, long)]
    input: PathBuf,

    /// Output parquet file
    #[arg(short, long, default_value = "usb_packets.parquet")]
    output: PathBuf,

    /// Device address filter (auto-detected from filename if not provided)
    #[arg(short, long)]
    device_address: Option<u8>,

    /// Session ID for this capture (auto-detected from filename if not provided)
    #[arg(long)]
    session_id: Option<String>,

    /// Append to existing parquet file instead of overwriting
    #[arg(long)]
    append: bool,

    /// Only capture packets with payload data (exclude control/setup packets)
    #[arg(long)]
    payload_only: bool,

    /// Verbose output
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct UsbPacketRecord {
    session_id: String,
    frame_number: u32,
    timestamp: f64,
    timestamp_absolute: String,
    direction: String,
    device_address: u8,
    bus_id: u8,
    endpoint_address: String,
    endpoint_number: u8,
    transfer_type: String,
    urb_type: String,
    urb_status: String,
    data_length: u32,
    urb_length: u32,
    payload_hex: String,
    payload_bytes_hex: String,
    // Additional USB metadata
    setup_flag: String,
    data_flag: String,
    interval: u32,
    start_frame: u32,
    // Frame-level metadata
    frame_length: u32,
    frame_protocols: String,
    source_file: String,
    added_datetime: String,
}

fn main() -> Result<()> {
    let mut args = Cli::parse();

    // Auto-detect device address from filename if not provided
    let device_address = if let Some(addr) = args.device_address {
        addr
    } else {
        let filename = args.input.file_name().and_then(|s| s.to_str()).unwrap_or("");
        // Look for pattern like "filename.16.pcapng" where 16 is the device address
        if let Some(dot_pos) = filename.rfind('.') {
            let before_ext = &filename[..dot_pos];
            if let Some(second_dot_pos) = before_ext.rfind('.') {
                let potential_id = &before_ext[second_dot_pos + 1..];
                if let Ok(id) = potential_id.parse::<u8>() {
                    println!("Auto-detected device address from filename: {}", id);
                    args.device_address = Some(id);
                    id
                } else {
                    return Err("Could not auto-detect device address from filename. Please provide --device-address".into());
                }
            } else {
                return Err("Could not auto-detect device address from filename. Please provide --device-address".into());
            }
        } else {
            return Err("Could not auto-detect device address from filename. Please provide --device-address".into());
        }
    };

    // Auto-detect session ID from filename if not provided
    let session_id = if let Some(id) = &args.session_id {
        id.clone()
    } else {
        let filename = args.input.file_name().and_then(|s| s.to_str()).unwrap_or("");
        if let Some(dot_pos) = filename.rfind('.') {
            let before_ext = &filename[..dot_pos];
            before_ext.to_string()
        } else {
            filename.to_string()
        }
    };

    println!("Processing file: {:?}", args.input);
    println!("Output file: {:?}", args.output);
    println!("Device address: {}", device_address);
    println!("Session ID: {}", session_id);
    if args.payload_only {
        println!("Mode: payload-only (excluding control/setup packets)");
    } else {
        println!("Mode: complete capture (all USB packets to device)");
    }

    // Build tshark filter with minimal essential filtering
    let mut filter_parts = vec![
        format!("usb.device_address == {}", device_address)
    ];
    
    // Add capdata filter only if payload-only mode is requested
    if args.payload_only {
        filter_parts.push("usb.capdata".to_string());
    }
    
    let display_filter = filter_parts.join(" && ");

    if args.verbose {
        println!("Display filter: {}", display_filter);
    }

    let file_path = args.input.to_str().ok_or("File path is not valid UTF-8")?;

    let mut rtshark = RTSharkBuilder::builder()
        .input_path(file_path)
        .display_filter(&display_filter)
        .spawn()?;

    let mut records = Vec::new();
    let mut packet_count = 0;

    println!("Reading packets...");
    while let Some(packet) = rtshark.read()? {
        packet_count += 1;

        if packet_count % 100 == 0 {
            println!("Processed {} packets...", packet_count);
        }

        if let Ok(record) = process_packet(packet, &session_id, args.verbose) {
            records.push(record);
        }
    }

    println!(
        "Processed {} packets, extracted {} USB data packets",
        packet_count,
        records.len()
    );

    if records.is_empty() {
        println!("No USB data packets found. Check your filter settings.");
        return Ok(());
    }

    // Convert to Polars DataFrame
    let new_df = create_dataframe(records)?;
    
    // Handle file merging/appending
    let final_df = if args.append && args.output.exists() {
        println!("Loading existing data from {:?}", args.output);
        let existing_df = LazyFrame::scan_parquet(PlPath::new(args.output.to_str().unwrap()), ScanArgsParquet::default())?
            .collect()?;
        
        // Check for duplicate session_id
        let existing_sessions: Vec<String> = existing_df
            .column("session_id")?
            .unique()?
            .str()?
            .into_no_null_iter()
            .map(|s| s.to_string())
            .collect();
        
        if existing_sessions.contains(&session_id) {
            return Err(format!(
                "Session ID '{}' already exists in {:?}. Use a different session ID or remove --append",
                session_id, args.output
            ).into());
        }
        
        // Combine datasets using vstack
        let combined_df = existing_df.vstack(&new_df)?;
        
        println!("Combined {} existing + {} new = {} total records", 
                existing_df.height(), new_df.height(), combined_df.height());
        
        combined_df
    } else {
        if args.output.exists() && !args.append {
            println!("Overwriting existing file: {:?}", args.output);
        }
        new_df
    };
    
    // Save to Parquet
    println!("Saving to Parquet file: {:?}", args.output);
    let mut file = std::fs::File::create(&args.output)?;
    ParquetWriter::new(&mut file).finish(&mut final_df.clone())?;

    println!("Successfully saved {} records to {:?}", final_df.height(), args.output);

    // Print some statistics
    print_statistics(&final_df)?;

    Ok(())
}

fn process_packet(packet: RtSharkPacket, session_id: &str, verbose: bool) -> Result<UsbPacketRecord> {
    // Extract frame-level information
    let frame_layer = packet.layer_name("frame").ok_or("Missing frame layer")?;
    
    let frame_num = frame_layer
        .metadata("frame.number")
        .and_then(|n| n.value().parse().ok())
        .unwrap_or(0);

    let timestamp = frame_layer
        .metadata("frame.time_relative")
        .and_then(|n| n.value().parse().ok())
        .unwrap_or(0.0);

    let timestamp_absolute = frame_layer
        .metadata("frame.time")
        .map(|t| t.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let frame_length: u32 = frame_layer
        .metadata("frame.len")
        .and_then(|l| l.value().parse().ok())
        .unwrap_or(0);

    let frame_protocols = frame_layer
        .metadata("frame.protocols")
        .map(|p| p.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    // Extract USB layer information
    let usb_layer = packet.layer_name("usb").ok_or("Missing USB layer")?;
    
    let direction = match usb_layer.metadata("usb.endpoint_address.direction").map(|d| d.value()) {
        Some("0") => "H->D".to_string(),
        Some("1") => "D->H".to_string(),
        _ => "Unknown".to_string(),
    };

    let device_address: u8 = usb_layer
        .metadata("usb.device_address")
        .and_then(|d| d.value().parse().ok())
        .unwrap_or(0);

    let bus_id: u8 = usb_layer
        .metadata("usb.bus_id")
        .and_then(|b| b.value().parse().ok())
        .unwrap_or(0);

    let endpoint_address = usb_layer
        .metadata("usb.endpoint_address")
        .map(|e| e.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let endpoint_number: u8 = usb_layer
        .metadata("usb.endpoint_address.number")
        .and_then(|n| n.value().parse().ok())
        .unwrap_or(0);

    let transfer_type = usb_layer
        .metadata("usb.transfer_type")
        .map(|t| t.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let urb_type = usb_layer
        .metadata("usb.urb_type")
        .map(|u| u.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let urb_status = usb_layer
        .metadata("usb.urb_status")
        .map(|s| s.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let data_length: u32 = usb_layer
        .metadata("usb.data_len")
        .and_then(|d| d.value().parse().ok())
        .unwrap_or(0);

    let urb_length: u32 = usb_layer
        .metadata("usb.urb_len")
        .and_then(|l| l.value().parse().ok())
        .unwrap_or(0);

    let setup_flag = usb_layer
        .metadata("usb.setup_flag")
        .map(|s| s.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let data_flag = usb_layer
        .metadata("usb.data_flag")
        .map(|d| d.value().to_string())
        .unwrap_or_else(|| "Unknown".to_string());

    let interval: u32 = usb_layer
        .metadata("usb.interval")
        .and_then(|i| i.value().parse().ok())
        .unwrap_or(0);

    let start_frame: u32 = usb_layer
        .metadata("usb.start_frame")
        .and_then(|s| s.value().parse().ok())
        .unwrap_or(0);

    // Extract hex payload (might be empty for control packets)
    let payload_hex = usb_layer.metadata("usb.capdata")
        .map(|p| p.value().to_string())
        .unwrap_or_else(|| String::new());

    // Clean up hex string (remove colons)
    let clean_hex = payload_hex.replace(':', "");

    // Convert hex to bytes (handle empty payloads)
    let payload_bytes = if clean_hex.is_empty() {
        Vec::new()
    } else {
        hex::decode(&clean_hex)
            .map_err(|e| format!("Failed to decode hex payload '{}': {}", clean_hex, e))?
    };

    if verbose {
        println!(
            "Frame {}: {} bytes {} @ {:.6}s [{}:{}]",
            frame_num, payload_bytes.len(), direction, timestamp, bus_id, endpoint_number
        );
    }

    let record = UsbPacketRecord {
        session_id: session_id.to_string(),
        frame_number: frame_num,
        timestamp,
        timestamp_absolute,
        direction,
        device_address,
        bus_id,
        endpoint_address,
        endpoint_number,
        transfer_type,
        urb_type,
        urb_status,
        data_length,
        urb_length,
        payload_hex: clean_hex.clone(),
        payload_bytes_hex: hex::encode(&payload_bytes),
        setup_flag,
        data_flag,
        interval,
        start_frame,
        frame_length,
        frame_protocols,
        source_file: session_id.to_string(), // Use session_id as source file identifier
        added_datetime: chrono::Utc::now().to_rfc3339(),
    };

    Ok(record)
}

fn create_dataframe(records: Vec<UsbPacketRecord>) -> Result<DataFrame> {
    let session_ids: Vec<String> = records.iter().map(|r| r.session_id.clone()).collect();
    let frame_numbers: Vec<u32> = records.iter().map(|r| r.frame_number).collect();
    let timestamps: Vec<f64> = records.iter().map(|r| r.timestamp).collect();
    let timestamp_absolutes: Vec<String> = records.iter().map(|r| r.timestamp_absolute.clone()).collect();
    let directions: Vec<String> = records.iter().map(|r| r.direction.clone()).collect();
    let device_addresses: Vec<u32> = records.iter().map(|r| r.device_address as u32).collect();
    let bus_ids: Vec<u32> = records.iter().map(|r| r.bus_id as u32).collect();
    let endpoint_addresses: Vec<String> = records.iter().map(|r| r.endpoint_address.clone()).collect();
    let endpoint_numbers: Vec<u32> = records.iter().map(|r| r.endpoint_number as u32).collect();
    let transfer_types: Vec<String> = records.iter().map(|r| r.transfer_type.clone()).collect();
    let urb_types: Vec<String> = records.iter().map(|r| r.urb_type.clone()).collect();
    let urb_statuses: Vec<String> = records.iter().map(|r| r.urb_status.clone()).collect();
    let data_lengths: Vec<u32> = records.iter().map(|r| r.data_length).collect();
    let urb_lengths: Vec<u32> = records.iter().map(|r| r.urb_length).collect();
    let payload_hexs: Vec<String> = records.iter().map(|r| r.payload_hex.clone()).collect();
    let payload_bytes_hex: Vec<String> = records.iter().map(|r| r.payload_bytes_hex.clone()).collect();
    let setup_flags: Vec<String> = records.iter().map(|r| r.setup_flag.clone()).collect();
    let data_flags: Vec<String> = records.iter().map(|r| r.data_flag.clone()).collect();
    let intervals: Vec<u32> = records.iter().map(|r| r.interval).collect();
    let start_frames: Vec<u32> = records.iter().map(|r| r.start_frame).collect();
    let frame_lengths: Vec<u32> = records.iter().map(|r| r.frame_length).collect();
    let frame_protocols: Vec<String> = records.iter().map(|r| r.frame_protocols.clone()).collect();
    let source_files: Vec<String> = records.iter().map(|r| r.source_file.clone()).collect();
    let added_datetimes: Vec<String> = records.iter().map(|r| r.added_datetime.clone()).collect();

    let df = df! [
        "session_id" => session_ids,
        "frame_number" => frame_numbers,
        "timestamp" => timestamps,
        "timestamp_absolute" => timestamp_absolutes,
        "direction" => directions,
        "device_address" => device_addresses,
        "bus_id" => bus_ids,
        "endpoint_address" => endpoint_addresses,
        "endpoint_number" => endpoint_numbers,
        "transfer_type" => transfer_types,
        "urb_type" => urb_types,
        "urb_status" => urb_statuses,
        "data_length" => data_lengths,
        "urb_length" => urb_lengths,
        "payload_hex" => payload_hexs,
        "payload_bytes_hex" => payload_bytes_hex,
        "setup_flag" => setup_flags,
        "data_flag" => data_flags,
        "interval" => intervals,
        "start_frame" => start_frames,
        "frame_length" => frame_lengths,
        "frame_protocols" => frame_protocols,
        "source_file" => source_files,
        "added_datetime" => added_datetimes,
    ]?;

    Ok(df)
}

fn print_statistics(df: &DataFrame) -> Result<()> {
    println!("\n=== Statistics ===");
    println!("Total records: {}", df.height());
    println!("Columns: {:?}", df.get_column_names());
    
    // Use lazy evaluation for statistics
    let lazy_df = df.clone().lazy();
    
    // Basic counts using group_by
    let direction_stats = lazy_df
        .clone()
        .group_by([col("direction")])
        .agg([len().alias("count")])
        .sort(["count"], SortMultipleOptions::default().with_order_descending(true))
        .collect()?;
    
    println!("\nDirection distribution:");
    println!("{}", direction_stats);
    
    let device_stats = lazy_df
        .clone()
        .group_by([col("device_address")])
        .agg([len().alias("count")])
        .sort(["count"], SortMultipleOptions::default().with_order_descending(true))
        .collect()?;
    
    println!("\nDevice address distribution:");
    println!("{}", device_stats);
    
    // Data length statistics
    let length_stats = lazy_df
        .clone()
        .select([
            col("data_length").mean().alias("avg_length"),
            col("data_length").min().alias("min_length"),
            col("data_length").max().alias("max_length"),
        ])
        .collect()?;
    
    println!("\nPayload length statistics:");
    println!("{}", length_stats);
    
    // Time range statistics
    let time_stats = lazy_df
        .clone()
        .select([
            col("timestamp").min().alias("start_time"),
            col("timestamp").max().alias("end_time"),
            (col("timestamp").max() - col("timestamp").min()).alias("duration"),
        ])
        .collect()?;
    
    println!("\nTime range:");
    println!("{}", time_stats);

    Ok(())
}