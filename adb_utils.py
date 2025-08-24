import subprocess
import os
from datetime import datetime

# ANSI escape codes for colors
GREEN = "\033[92m"
RESET = "\033[0m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"

def run_adb_command(command):
    """
    Executes an ADB command.
    Returns a tuple: (success_status: bool, stdout: str, stderr: str).
    success_status is True if command ran without CalledProcessError.
    """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except FileNotFoundError:
        return False, "", "Error: 'adb' command not found. Please ensure ADB is installed and added to your system's PATH."
    except Exception as e:
        return False, "", f"An unexpected error occurred: {e}"

def get_adb_shell_prop_output():
    """
    Executes 'adb shell getprop' and returns its stdout.
    Handles errors internally but does not print success output.
    """
    try:
        result = subprocess.run("adb shell getprop", shell=True, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"\n{RED}Error fetching raw device properties: {e}{RESET}")
        print(f"{RED}Stderr: {e.stderr}{RESET}")
        return None
    except FileNotFoundError:
        print(f"\n{RED}Error: 'adb' command not found.{RESET}")
        print(f"{YELLOW}Please ensure ADB is installed and added to your system's PATH.{RESET}")
        return None
    except Exception as e:
        print(f"\n{RED}An unexpected error occurred while fetching properties: {e}{RESET}")
        return None

def get_device_info():
    """
    Fetches desired device properties and returns them as a dictionary.
    """
    prop_output = get_adb_shell_prop_output()
    device_info = {
        "net.bt.name": "N/A",
        "ro.product.model": "N/A",
        "ro.product.manufacturer": "N/A",
        "net.hostname": "N/A"
    }
    desired_props = {
        "net.bt.name",
        "ro.product.model",
        "ro.product.manufacturer",
        "net.hostname"
    }

    if prop_output:
        for line in prop_output.splitlines():
            if line.startswith('[') and ']: [' in line and line.endswith(']'):
                try:
                    key_part, value_part = line.split(']: [', 1)
                    key = key_part[1:]
                    value = value_part[:-1]
                    if key in desired_props:
                        device_info[key] = value
                except ValueError:
                    continue
    return device_info

def get_storage_details():
    """
    Fetches and returns storage details (total, used, available, percentage)
    for all detected storage paths.
    Returns a list of dictionaries, each containing details for a storage.
    """
    # Moved import here to resolve circular dependency
    from adb_Browse import get_device_storages 

    storages = get_device_storages()
    all_storage_details = []

    print(f"\n{BLUE}--- Fetching Storage Details ---{RESET}")
    if not storages:
        print(f"{YELLOW}No accessible storage locations found on the device or 'adb_Browse.py' not accessible.{RESET}")
        return []

    # Get df -k output once for all storages to reduce adb calls
    success_df, stdout_df, stderr_df = run_adb_command("adb shell df -k")
    df_lines = []
    if success_df:
        df_lines = stdout_df.strip().split('\n')
    else:
        print(f"{YELLOW}Warning: Could not get detailed storage info from 'df -k'. Error: {stderr_df.strip()}{RESET}")
        print(f"{YELLOW}Storage details might be incomplete.{RESET}")

    for name, path in storages: # 'path' here will now be the resolved path from adb_Browse.py
        details = {
            "name": name,
            "path": path,
            "total_gb": "N/A",
            "used_gb": "N/A",
            "available_gb": "N/A",
            "percentage_used": "N/A"
        }

        # Find the relevant line in df -k output
        found_df_data = False
        for line in df_lines:
            # Split by spaces, and check if the last part (Mounted on) matches the path
            parts = line.split()
            if len(parts) >= 6:
                mount_point = parts[-1]
                
                # Check if the df mount_point matches the 'path' provided (which should now be canonical)
                # Or if the path is an internal storage canonical path and the mount_point is also an internal alias from df
                is_internal_canonical_path = (
                    path == "/storage/emulated/0" or 
                    path == "/storage/emulated" or # Check if the passed path is '/storage/emulated'
                    path == "/sdcard" # This might be the canonical for some devices too
                )
                
                is_df_internal_mount = (
                    mount_point == "/storage/emulated/0" or 
                    mount_point == "/storage/emulated" or # ADDED to cover user's df output
                    mount_point == "/sdcard" 
                )

                if mount_point == path or (is_internal_canonical_path and is_df_internal_mount):
                    try:
                        total_kblocks = int(parts[1])
                        used_kblocks = int(parts[2])
                        available_kblocks = int(parts[3])

                        total_gb = total_kblocks / (1024**2) # Convert KB to GB
                        used_gb = used_kblocks / (1024**2)
                        available_gb = available_kblocks / (1024**2)
                        
                        details["total_gb"] = f"{total_gb:.2f} GB"
                        details["used_gb"] = f"{used_gb:.2f} GB"
                        details["available_gb"] = f"{available_gb:.2f} GB"
                        details["percentage_used"] = f"{(used_kblocks / total_kblocks) * 100 if total_kblocks > 0 else 0 :.2f}%"
                        found_df_data = True
                        break # Found the line for this path
                    except (ValueError, IndexError) as e:
                        print(f"{YELLOW}Warning: Error parsing df -k line for '{path}' (or its alias): {line}. Error: {e}{RESET}")
                        continue # Try next line

        if not found_df_data:
            print(f"{YELLOW}Warning: Could not find or parse 'df -k' data for '{path}'.{RESET}")
        
        all_storage_details.append(details)
    return all_storage_details

def get_top_large_folders(path, count=5):
    """
    Finds the top N largest folders (direct subdirectories) in a given path.
    Returns a list of (formatted_size_str, folder_path) tuples, sorted descending by size.
    """
    print(f"{BLUE}--- Searching for top {count} largest folders in '{path}' (this may take a moment) ---{RESET}")
    
    # List direct contents of the path, including files and directories
    # -a includes hidden files/directories, -F appends / to directories
    success_ls, stdout_ls, stderr_ls = run_adb_command(f"adb shell ls -aF \"{path}\"")

    if not success_ls:
        print(f"{YELLOW}Warning: Could not list contents of '{path}'. Error: {stderr_ls.strip()}{RESET}")
        return []
    
    potential_items = []
    for line in stdout_ls.splitlines():
        item_name = line.strip()
        if item_name and item_name not in (".", ".."): # Exclude current and parent directory links
            full_item_path = os.path.join(path, item_name).replace("\\", "/") # Ensure forward slashes

            potential_items.append(full_item_path)

    if not potential_items:
        print(f"{YELLOW}No significant items found in '{path}' for size calculation.{RESET}")
        return []

    folder_sizes_raw = [] # Stores (size_in_bytes, original_du_output_line)

    # Execute 'du -sh' for each direct item (file or directory)
    for item_path in potential_items:
        success_du, stdout_du, stderr_du = run_adb_command(f"adb shell du -sh \"{item_path}\"")
        if success_du and stdout_du:
            line = stdout_du.strip()
            parts = line.split('\t')
            if len(parts) == 2:
                size_str = parts[0].strip()
                try:
                    # Parse size string (e.g., "1.2G", "869M") to bytes for sorting
                    size_val = float(size_str[:-1]) if size_str and size_str[-1].isalpha() else float(size_str)
                    unit = size_str[-1].upper() if size_str and size_str[-1].isalpha() else ''
                    
                    if unit == 'G':
                        size_bytes = size_val * (1024**3)
                    elif unit == 'M':
                        size_bytes = size_val * (1024**2)
                    elif unit == 'K':
                        size_bytes = size_val * 1024
                    elif unit == 'B' or unit == '': # Assume bytes if no unit or 'B'
                        size_bytes = size_val
                    else: # Fallback if unit not recognized
                        size_bytes = 0 # Or handle error appropriately
                    
                    folder_sizes_raw.append((size_bytes, f"{size_str} {item_path}"))
                except ValueError:
                    continue # Skip if size parsing fails
        elif stderr_du:
            # Suppress individual du errors to avoid clutter, especially for permission denied or nonexistent files
            pass 

    # Sort by size in descending order
    folder_sizes_raw.sort(key=lambda x: x[0], reverse=True)
    
    # Return top N formatted strings
    return [f"{display_str}" for size_bytes, display_str in folder_sizes_raw[:count]]


def check_adb_status():
    """
    Checks if ADB is installed and if a device is connected, with colored output.
    Returns True if ADB is ready and device authorized, False otherwise.
    """
    print(f"{BLUE}Checking ADB status...{RESET}")
    try:
        result = subprocess.run("adb devices", shell=True, capture_output=True, text=True, check=True)
        output = result.stdout
        print(f"{BLUE}{output}{RESET}")
        if "List of devices attached" in output:
            lines = output.strip().split('\n')
            if len(lines) > 1 and not any("offline" in line or "unauthorized" in line for line in lines[1:]):
                print(f"{GREEN}ADB is installed and a device is connected and authorized.{RESET}")
                return True
            else:
                print(f"{YELLOW}ADB is installed, but no authorized device is connected or device is offline/unauthorized.{RESET}")
                print(f"{YELLOW}Please ensure your device is connected, USB debugging is enabled, and you've authorized the connection on your phone.{RESET}")
                return False
        else:
            print(f"{RED}ADB command did not return expected output. Is ADB installed correctly?{RESET}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error checking ADB status: {e.stderr}{RESET}")
        print(f"{YELLOW}Please ensure ADB is installed and added to your system's PATH.{RESET}")
        return False
    except FileNotFoundError:
        print(f"{RED}Error: 'adb' command not found.{RESET}")
        print(f"{YELLOW}Please ensure ADB is installed and added to your system's PATH.{RESET}")
        return False

def kill_and_restart_adb_server():
    """Kills and restarts the ADB server."""
    confirm = input(f"{YELLOW}Are you sure you want to kill and restart the ADB server? This might temporarily disconnect all devices. (yes/no): {RESET}").lower()
    if confirm == 'yes':
        print(f"{GREEN}Killing ADB server...{RESET}")
        run_adb_command("adb kill-server")
        print(f"{GREEN}Starting ADB server...{RESET}")
        run_adb_command("adb start-server")
        print(f"{GREEN}ADB server restarted. Please check device connection (Option 1).{RESET}")
    else:
        print(f"{YELLOW}Killing and restarting ADB server cancelled.{RESET}")

def enter_adb_shell():
    """Enters an interactive ADB shell."""
    print(f"\n{GREEN}Entering ADB Shell. Type 'exit' to return to the main menu.{RESET}")
    print(f"{GREEN}-----------------------------------{RESET}")
    try:
        subprocess.call("adb shell", shell=True)
    except FileNotFoundError:
        print(f"{RED}Error: 'adb' command not found. Ensure ADB is in your PATH.{RESET}")
    print(f"{GREEN}-----------------------------------{RESET}")
    print(f"{GREEN}Exited ADB Shell.{RESET}")

def list_connected_devices_and_details():
    """Lists connected ADB devices and fetches their properties, storage details, and top folders."""
    print(f"{GREEN}--- Listing Connected Devices ---{RESET}")
    try:
        result = subprocess.run("adb devices", shell=True, capture_output=True, text=True, check=True)
        output_lines = result.stdout.strip().split('\n') 
        print(f"{GREEN}{result.stdout}{RESET}")

        device_status_found = False
        for line in output_lines[1:]: # Skip the "List of devices attached" header
            if "\tdevice" in line:
                print(f"{GREEN}Android USB Debugging Mode: ON (Authorized){RESET}")
                device_status_found = True
                break
            elif "\tunauthorized" in line:
                print(f"{YELLOW}Android USB Debugging Mode: ON (Unauthorized){RESET}")
                print(f"{YELLOW}Please check your Android device screen and accept the USB debugging authorization prompt.{RESET}")
                device_status_found = True
                break
            elif "\toffline" in line:
                print(f"{YELLOW}Android USB Debugging Mode: Possibly ON, but device is OFFLINE.{RESET}")
                print(f"{YELLOW}Ensure your device is connected, powered on, and not in a low-power state.{RESET}")
                device_status_found = True
                break

        if not device_status_found and len(output_lines) <= 1:
            print(f"{RED}Android USB Debugging Mode: OFF or Device Not Connected.{RESET}")
            print(f"{YELLOW}Please enable USB Debugging in Developer Options on your Android device and connect it via USB.{RESET}")
            print(f"{YELLOW}If already enabled, ensure the USB connection mode is set to 'File Transfer' or 'PTP'.{RESET}")

    except subprocess.CalledProcessError as e:
        print(f"{RED}Error running 'adb devices': {e.stderr}{RESET}")
    except FileNotFoundError:
        print(f"{RED}Error: 'adb' command not found. Ensure ADB is in your PATH.{RESET}")
    
    print(f"\n{GREEN}--- Device Properties ---{RESET}")
    device_props = get_device_info()
    
    # Display device properties
    print(f"{GREEN}Device Name: {device_props.get('net.bt.name', 'N/A')}{RESET}")
    print(f"{GREEN}Model: {device_props.get('ro.product.model', 'N/A')}{RESET}")
    print(f"{GREEN}Manufacturer: {device_props.get('ro.product.manufacturer', 'N/A')}{RESET}")
    print(f"{GREEN}Hostname: {device_props.get('net.hostname', 'N/A')}{RESET}")

    # Display additional properties if available
    prop_output = get_adb_shell_prop_output()
    if prop_output:
        desired_props_full = {
            "ro.product.name", "ro.oxygen.version", 
            "ro.build.description", "ro.build.kernel.id", "ro.build.soft.version",
            "ro.build.version.ota", "ro.product.cpu.abilist", "ro.system.build.date"
        }
        found_additional_props = {}
        for line in prop_output.splitlines():
            if line.startswith('[') and ']: [' in line and line.endswith(']'):
                try:
                    key_part, value_part = line.split(']: [', 1)
                    key = key_part[1:]
                    value = value_part[:-1]
                    if key in desired_props_full:
                        found_additional_props[key] = value
                except ValueError:
                    continue
        
        ordered_additional_keys = [
            "ro.product.name",
            "ro.oxygen.version",
            "ro.build.description",
            "ro.build.kernel.id",
            "ro.build.soft.version",
            "ro.build.version.ota",
            "ro.product.cpu.abilist",
            "ro.system.build.date"
        ]
        for key in ordered_additional_keys:
            if key in found_additional_props:
                print(f"{GREEN}[{key}]: [{found_additional_props[key]}]{RESET}")
            else:
                print(f"{YELLOW}[{key}]: [Not Found]{RESET}")
    else:
        print(f"{RED}Could not retrieve full device properties.{RESET}")

    print(f"{GREEN}-----------------------------------{RESET}")

    # Display storage details
    storage_details = get_storage_details()
    
    # Prepare consolidated storage information for cleaner output
    consolidated_storage_info = {}
    internal_storage_0_found = False
    
    for store in storage_details:
        if store['path'] == "/storage/emulated/0":
            consolidated_storage_info["Internal Storage"] = store
            internal_storage_0_found = True
        elif store['path'] == "/storage/emulated" and not internal_storage_0_found:
            # Only add /storage/emulated if /storage/emulated/0 wasn't explicitly found first
            consolidated_storage_info["Internal Storage"] = store
        elif "SD Card" in store['name'] or "External Storage" in store['name']:
             consolidated_storage_info[store['name']] = store
        else: # Catch any other unknown storages
            consolidated_storage_info[store['name']] = store


    if consolidated_storage_info:
        print(f"\n{GREEN}--- Storage Information ---{RESET}")
        for storage_name, store in consolidated_storage_info.items():
            print(f"{BLUE}Storage: {storage_name} ({store['path']}){RESET}")
            print(f"{BLUE}| Metric          | Value          |{RESET}")
            print(f"{BLUE}|:----------------|:---------------|{RESET}")
            print(f"{BLUE}| Total Storage   | {store['total_gb']:<14} |{RESET}")
            print(f"{BLUE}| Used Storage    | {store['used_gb']} ({store['percentage_used']}){RESET}")
            print(f"{BLUE}| Available Storage| {store['available_gb']:<14} |{RESET}")
            
            # Display top 5 folders for this storage
            top_folders = get_top_large_folders(store['path'], count=5)
            if top_folders:
                print(f"{BLUE}  Top 5 Largest Items:{RESET}")
                for folder in top_folders:
                    print(f"{BLUE}    - {folder}{RESET}")
            else:
                print(f"{YELLOW}  Could not retrieve top items for this storage or it's empty/inaccessible.{RESET}")
            print(f"{GREEN}-----------------------------------{RESET}\n")
    else:
        print(f"{RED}No storage details could be retrieved.{RESET}")
    
    input(f"{YELLOW}Press Enter to return to menu.{RESET}")