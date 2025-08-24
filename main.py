from adb_utils import check_adb_status, GREEN, RESET, RED, BLUE, YELLOW
from adb_utils import list_connected_devices_and_details, enter_adb_shell, kill_and_restart_adb_server
from adb_Browse import browse_mobile_storage
from adb_backup_restore import backup_mobile_to_pc, push_pc_to_mobile, backup_all_user_data

def display_menu():
    """
    Displays the main menu options to the user.
    """
    print(f"\n{BLUE}--- Android ADB Automation Menu ---{RESET}")
    print(f"{BLUE}1. List Connected Devices & Details{RESET}")
    print(f"{BLUE}2. Browse Mobile Storage{RESET}") # Updated
    print(f"{BLUE}3. Backup data from Mobile --> PC{RESET}")
    print(f"{BLUE}4. Push data from PC --> Mobile{RESET}")
    print(f"{BLUE}5. Backup All User Data from MOBILE --> PC (skipping system data and empty directories){RESET}")
    print(f"{BLUE}6. Enter ADB Shell (Type 'exit' to return to menu){RESET}")
    print(f"{BLUE}7. Kill and Restart ADB Server{RESET}")
    print(f"{BLUE}0. Exit{RESET}")
    print(f"{BLUE}-----------------------------------{RESET}")

def main():
    """
    Main function to run the ADB automation script.
    """
    if not check_adb_status():
        print(f"{RED}Exiting due to ADB or device connection issues.{RESET}")
        return

    while True:
        display_menu()
        choice = input(f"{YELLOW}Enter your choice (0-7): {RESET}")
        print(f"{GREEN}You selected option: {choice}{RESET}")

        if choice == '1':
            list_connected_devices_and_details()
        elif choice == '2':
            browse_mobile_storage()
        elif choice == '3':
            backup_mobile_to_pc()
        elif choice == '4':
            push_pc_to_mobile()
        elif choice == '5':
            backup_all_user_data()
        elif choice == '6':
            enter_adb_shell()
        elif choice == '7':
            kill_and_restart_adb_server()
        elif choice == '0':
            print(f"{GREEN}Exiting ADB Automation script. Goodbye!{RESET}")
            break
        else:
            print(f"{RED}Invalid choice. Please enter a number between 0 and 7.{RESET}")

if __name__ == "__main__":
    main()