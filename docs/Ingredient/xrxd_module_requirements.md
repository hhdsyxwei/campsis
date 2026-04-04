# XRXD Module Requirements Document

## 1. Module Overview

The XRXD module is a dividend and bonus data downloader responsible for fetching stock dividend and bonus data from the Baostock API and storing it in the database.

## 2. Terminology

### 2.1 Task
- **Definition**: A task represents a collection of download blocks within a specific range
- **Scope**: Typically corresponds to a complete download operation, containing multiple blocks across different years and stocks
- **Identification**: Each task is identified by a task type (e.g., 'xrxd', 'kline')
- **State Management**: Task state is tracked through download pointers, which indicate the current progress

### 2.2 Block
- **Definition**: A block is a collection of data for one stock in one year
- **Uniqueness**: Each block is uniquely identified by (year, stock_code)
- **Ordering**: Blocks are ordered first by year (ascending), then by stock code order in the `stock_fixed_seq` table
- **Processing**: Each block is processed as a single unit during download

### 2.3 Pointer
- **Definition**: A pointer is a reference to the current download block
- **Purpose**: Tracks the progress of the download task
- **State Indicator**: The pointer's value indicates the current download state:
  - Empty pointer: Download completed
  - Non-empty pointer: Download in progress, pointing to the current block
- **Update**: The pointer is updated before each block download to ensure breakpoint resume capability

## 3. Core Functional Requirements

### 3.1 Data Download
- Support downloading dividend and bonus data by year and stock code
- Use Baostock API to retrieve raw data
- Support data cleaning and processing
- Support data storage to database

### 3.2 Download Order
- Adopt year-first, stock-code-second download order
- Years arranged in ascending order
- Stock code order based on the fixed sequence in the `stock_fixed_seq` table

### 3.3 Resume from Breakpoint
- Support resuming downloads from interruption points
- Record current progress during download
- Support continuing from last interruption point after program restart

### 3.4 Download from Scratch
- Support clearing previous download records and starting from scratch
- Provide dedicated interface for downloading from scratch

## 4. State Management Requirements

### 4.1 State Definitions

| State | Condition | Description |
|------|------|------|
| **Download Not Started** | No corresponding task type record exists in database | Task record does not exist |
| **Download Completed** | Task record exists and all three-level pointers are empty | Primary, secondary, and tertiary pointer values are all empty strings |
| **Download In Progress** | Task record exists and pointer points to valid download block | Pointer value is not empty, pointing to specific download task |

### 4.2 State Management Interfaces

#### 4.2.1 Core Interfaces
- `task_exists(task_type)`: Query whether a task of specified type exists
- `is_download_pointer_empty(task_type)`: Determine if download pointer is empty
- `clear_download_pointer(task_type)`: Set download pointer to empty
- `delete_task(task_type)`: Delete task record of specified type

#### 4.2.2 State Query Flow
1. Check if task exists: call `task_exists`
2. If task does not exist, state is "Download Not Started"
3. If task exists, check if pointer is empty: call `is_download_pointer_empty`
4. If pointer is empty, state is "Download Completed"
5. If pointer is not empty, state is "Download In Progress"

### 4.3 State Transitions

1. **Initial State**: No task record → Download Not Started
2. **Start Download**: Create task record, pointer points to first task → Download In Progress
3. **Downloading**: Pointer continuously updates, pointing to current task → Download In Progress
4. **Download Completed**: Clear all pointers → Download Completed
5. **Restart Download**: Delete task record → Download Not Started

## 5. Interface Design

### 5.1 Class Methods

#### XrxdDownloader Class
- `__init__(db_conn)`: Initialize downloader
- `download_xrxd(start_year, end_year)`: Core download method, supports resume from breakpoint
- `download_xrxd_from_scratch(start_year, end_year)`: Download from scratch
- `get_download_status()`: Get current download status

### 5.2 Global Interfaces

- `continue_download_xrxd(db_conn, start_year, end_year)`: Continue download interface provided externally (supports resume from breakpoint)
- `start_new_xrxd_download(db_conn, start_year, end_year)`: Start new download interface provided externally (clears previous progress)

### 5.3 State Management Interfaces

#### GlobalDlCtrlBlockManager Class
- `task_exists(task_type)`: Query if task exists
- `is_download_pointer_empty(task_type)`: Determine if pointer is empty
- `clear_download_pointer(task_type)`: Clear pointer
- `delete_task(task_type)`: Delete task record
- `set_xrxd_progress(year, stock_code)`: Set XRXD download progress
- `get_xrxd_progress()`: Get XRXD download progress

## 6. Implementation Details

### 6.1 Data Download Flow
1. Check download status
2. If download completed, return directly
3. If download in progress, resume from breakpoint
4. If download not started, start from scratch
5. Loop through each download block
6. Update download pointer before each block download
7. Get next block after download completion
8. Clear download pointer after all blocks completed

### 6.2 Data Processing
- Retrieve raw data from Baostock API
- Clean data, handle null values and anomalies
- Transform data format to ensure compatibility with database table structure
- Store data to `stock_xrxd` table

### 6.3 Error Handling
- Capture exceptions during download process
- Record detailed error logs
- Propagate exceptions upward for caller to handle

## 7. Workflow

### 7.1 Resume from Breakpoint Flow
1. Call `continue_download_xrxd` method
2. Check download status
3. If status is "Download Completed", return directly
4. If status is "Download In Progress", resume from breakpoint
5. If status is "Download Not Started", start from scratch
6. Execute download blocks one by one
7. Clear download pointer after all blocks completed

### 7.2 Download from Scratch Flow
1. Call `start_new_xrxd_download` method
2. Delete task record
3. Call `continue_download_xrxd` method (status is now "Download Not Started")
4. Start downloading all blocks from scratch

## 8. Database Design

### 8.1 Table Structure

#### `stock_xrxd` Table
- Stores dividend and bonus data
- Contains stock code, year, dividend and bonus related fields

#### `global_dl_ctrl_block` Table
- Stores download control information
- Contains task type, pointer information, startup parameters, block count, etc.

### 8.2 Index Design
- `global_dl_ctrl_block` table has unique index on `task_type` field
- Ensures uniqueness of task types

## 9. Performance Optimization

### 9.1 Download Optimization
- Download by year and stock code order to avoid duplicate downloads
- Utilize fixed sequence in `stock_fixed_seq` table to reduce database queries

### 9.2 State Management Optimization
- Centralize download state management to avoid repeated queries
- Use database transactions to ensure atomicity of state updates

## 10. Extensibility

- Support adding new task types
- Support custom download order
- Support adding new data processing logic
- Support integration with other modules

## 11. Testing Recommendations

- Test resume from breakpoint functionality
- Test download from scratch functionality
- Test state management logic
- Test exception handling
- Test performance and reliability
