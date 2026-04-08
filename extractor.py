import io
import json
import subprocess
import re
from PIL import Image, ExifTags

def _convert_to_degrees(value) -> float | None:
    """Helper function to convert the GPS coordinates stored in the EXIF to decimal degrees for Leaflet.js"""
    try:
        # ExifTool fallback to string parse if string output (Validation format step)
        if isinstance(value, str):
            # Parse ExifTool strings like "34 12 55.00 N"
            parts = re.findall(r"[\d\.]+", value)
            if len(parts) >= 3:
                degrees = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return degrees + (minutes / 60.0) + (seconds / 3600.0)
            return float(value)

        # value is typically a tuple of IFDRational values e.g., (IFDRational(34, 1), IFDRational(12, 1), ...)
        # Fallback to fractional math if older PIL returns ((num, den), ...)
        if isinstance(value[0], tuple):
            d0, d1 = value[0]
            m0, m1 = value[1]
            s0, s1 = value[2]
            degrees = float(d0) / float(d1)
            minutes = float(m0) / float(m1)
            seconds = float(s0) / float(s1)
        else:
            degrees = float(value[0])
            minutes = float(value[1])
            seconds = float(value[2])

        return degrees + (minutes / 60.0) + (seconds / 3600.0)
    except Exception:
        return None

def _decode_exif_value(value):
    """Helper to clean up bytes or complex types returned by PIL Exif reader"""
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8', 'ignore').strip('\x00')
        except Exception:
            pass
    return str(value).strip('\x00') if value is not None else None

def parse_metadata(file_bytes: bytes) -> dict:
    """
    Parses EXIF payload fully in-memory using io.BytesIO.
    Returns structured data avoiding fatal errors as per constraints.
    Supports recursive ExifTool integration alongside Pillow binary deep scans.
    """
    metadata = {
        "format": None,
        "mode": None,
        "size": None,
        "device": {
            "Make": None,
            "Model": None,
            "LensModel": None,
            "Software": None
        },
        "forensics": {
            "DigitalZoomRatio": None,
            "SceneCaptureType": None,
            "UserComment": None,
            "XMP_Signature_Found": False,
            "IPTC_Signature_Found": False,
            "Hidden_MakerNote_0x927c": None,
            "Hidden_Tag_0x0100": None
        },
        "gps": None,
        "gps_status": "METADATA_STRIPPED_OR_MISSING"
    }

    try:
        # Pre-scan Binary Stream Native Check (Forensic level XMP/IPTC detection)
        if b"http://ns.adobe.com/xap/1.0/" in file_bytes:
            metadata["forensics"]["XMP_Signature_Found"] = True
        if b"Photoshop 3.0\x008BIM" in file_bytes or b"IPTC" in file_bytes:
            metadata["forensics"]["IPTC_Signature_Found"] = True

        # Try Advanced Subprocess Exiftool if available natively on system
        exiftool_proc_successful = False
        try:
            # Enforce the RAM execution constraints via pipe (-)
            # -c formats it reliably for our _convert_to_degrees function parsing
            proc = subprocess.run(
                ["exiftool", "-j", "-c", "%d %d %.8f", "-"],
                input=file_bytes,
                capture_output=True,
                check=True
            )
            raw_exif_json = json.loads(proc.stdout.decode('utf-8', errors='ignore'))
            
            if raw_exif_json and len(raw_exif_json) > 0:
                exif_data = raw_exif_json[0]
                exiftool_proc_successful = True
                
                # Fetch basic devices from EXIF
                metadata["device"]["Make"] = exif_data.get("Make")
                metadata["device"]["Model"] = exif_data.get("Model")
                metadata["device"]["Software"] = exif_data.get("Software")
                metadata["device"]["LensModel"] = exif_data.get("LensModel", exif_data.get("LensID"))

                # Forensics and hidden notes
                metadata["forensics"]["DigitalZoomRatio"] = exif_data.get("DigitalZoomRatio")
                metadata["forensics"]["SceneCaptureType"] = exif_data.get("SceneCaptureType")
                metadata["forensics"]["UserComment"] = exif_data.get("UserComment")
                metadata["forensics"]["Hidden_MakerNote_0x927c"] = "Detected" if "MakerNote" in exif_data else None
                metadata["forensics"]["Hidden_Tag_0x0100"] = exif_data.get("ImageWidth", exif_data.get("ExifImageWidth"))

                # Coordinate Extraction natively fed back into gps-converter skill formatting
                if "GPSLatitude" in exif_data and "GPSLongitude" in exif_data:
                    lat_str = exif_data["GPSLatitude"]
                    lng_str = exif_data["GPSLongitude"]
                    
                    lat_val = _convert_to_degrees(lat_str)
                    lng_val = _convert_to_degrees(lng_str)
                    
                    if lat_val is not None and lng_val is not None:
                        # Negate relative to string refs
                        if 'S' in lat_str or 'S' in exif_data.get("GPSLatitudeRef", "N"):
                            lat_val = -abs(lat_val)
                        if 'W' in lng_str or 'W' in exif_data.get("GPSLongitudeRef", "E"):
                            lng_val = -abs(lng_val)
                            
                        # Evaluate zeroed out explicitly protected bounds
                        if lat_val == 0.0 and lng_val == 0.0:
                            metadata["gps_status"] = "COORDINATES_ZEROED"
                        else:
                            metadata["gps_status"] = "SUCCESS"
                            metadata["gps"] = {
                                "lat": float(f"{lat_val:.6f}"),
                                "lng": float(f"{lng_val:.6f}")
                            }

        except Exception:
            pass # Safe Fallback to standard Pillow

        # Image loaded perfectly in memory (No disk saving) - Fallback or Supplemental Data
        image = Image.open(io.BytesIO(file_bytes))
        metadata["format"] = image.format
        metadata["mode"] = image.mode
        metadata["size"] = image.size

        # If ExifTool failed (fallback safely to deep PILLOW implementation)
        if not exiftool_proc_successful:
            exif_data = image.getexif()
            if not exif_data:
                return metadata

            # Standardize: Map EXIF tag IDs to human-readable string values via TAGS
            for tag_id, val in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                if tag_name in metadata["device"]:
                    metadata["device"][tag_name] = _decode_exif_value(val)
                # Recover unregistered/hidden
                if tag_id == 37500 or tag_name == 'MakerNote': # 0x927c
                    metadata["forensics"]["Hidden_MakerNote_0x927c"] = "Detected (Unparsed Binary)"
                if tag_id == 256: # 0x0100 ImageWidth hidden usage
                    metadata["forensics"]["Hidden_Tag_0x0100"] = _decode_exif_value(val)
                if tag_name in ["DigitalZoomRatio", "SceneCaptureType", "UserComment"]:
                    metadata["forensics"][tag_name] = _decode_exif_value(val)
                    
            # Device Deep-Dive: Specific tags like LensModel often live deeper inside the Exif IFD payload
            try:
                exif_ifd = exif_data.get_ifd(ExifTags.IFD.Exif)
                for tag_id, val in exif_ifd.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                    if tag_name in metadata["device"] and not metadata["device"][tag_name]:
                        metadata["device"][tag_name] = _decode_exif_value(val)
                    if tag_name in ["DigitalZoomRatio", "SceneCaptureType", "UserComment"]:
                        metadata["forensics"][tag_name] = _decode_exif_value(val)
            except Exception:
                pass

            # Nested GPS Parsing: Extract deeper GPSInfo payload specifically mapping internal GPSTAGS
            try:
                gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd:
                    metadata["gps_status"] = "COORDINATES_ZEROED"
                    gps_info = {}
                    for key, val in gps_ifd.items():
                        tag_name = ExifTags.GPSTAGS.get(key, key)
                        gps_info[tag_name] = val
                        
                    if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
                        lat_tuple = gps_info["GPSLatitude"]
                        lat_ref = gps_info.get("GPSLatitudeRef", "N")
                        lng_tuple = gps_info["GPSLongitude"]
                        lng_ref = gps_info.get("GPSLongitudeRef", "E")

                        if isinstance(lat_ref, bytes): lat_ref = lat_ref.decode('ascii', 'ignore').strip('\x00')
                        if isinstance(lng_ref, bytes): lng_ref = lng_ref.decode('ascii', 'ignore').strip('\x00')

                        lat_val = _convert_to_degrees(lat_tuple)
                        lng_val = _convert_to_degrees(lng_tuple)

                        if lat_val is not None and lng_val is not None:
                            if lat_ref == 'S': lat_val = -lat_val
                            if lng_ref == 'W': lng_val = -lng_val
                            
                            if lat_val != 0.0 or lng_val != 0.0:
                                metadata["gps_status"] = "SUCCESS"
                                metadata["gps"] = {"lat": float(f"{lat_val:.6f}"), "lng": float(f"{lng_val:.6f}")}
            except Exception:
                pass
                
    except Exception:
        pass

    return metadata
