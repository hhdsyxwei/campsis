# Generic Downloader Requirements Document

## 1. Project Background and Objectives

### 1.1 Project Background
Campsis is an enterprise-grade data intelligence platform aimed at empowering business decisions through data. The platform needs to obtain various financial data from multiple data sources. To ensure the reliability, efficiency, and maintainability of data acquisition, a generic downloader framework is required.

### 1.2 Project Objectives
The objectives of the generic downloader framework are:
- Provide a unified download process and status management mechanism
- Support breakpoint resume and fresh download functionality
- Unify data cleaning and storage processes
- Ensure the reliability and monitorability of the download process
- Facilitate extension to support new data types

## 2. Basic Concept Definitions

| Concept | Definition | Description |
|---------|------------|-------------|
| **Block** | Data organized together according to certain conditions | Conditions may include a certain range of time periods, specific or specific sets of security identifiers, or other appropriate conditions. A block is the smallest download unit, uniquely identified by these conditions |
| **Task** | Blocks arranged in a certain order | Represents a complete download operation, containing multiple blocks arranged in a specific order |
| **Pointer** | Used to track current download progress | Includes primary pointer (main condition, such as time period), secondary pointer (secondary condition, such as security identifier), and tertiary pointer (optional, for more granular progress tracking) |
| **Download Status** | Current status of the task | Includes: Not Started (`NOT_STARTED`), In Progress (`IN_PROGRESS`), Completed (`COMPLETED`) |

## 3. Functional Requirements (What to Do)

### 3.1 Core Functions
1. **Data Download**: Obtain raw data from the data source API
2. **Data Cleaning**: Handle null values, outliers, and convert data formats
3. **Data Storage**: Save cleaned data to the corresponding database table
4. **Breakpoint Resume**: Support resuming downloads from interruption points to avoid duplicate downloads
5. **Fresh Download**: Support clearing previous download records and starting from scratch

### 3.2 Auxiliary Functions
1. **Status Management**: Track and manage the status of download tasks
2. **Progress Calculation**: Calculate total blocks and current download progress
3. **Error Handling**: Capture and handle exceptions during download
4. **Logging**: Record detailed information about the download process

## 4. Non-Functional Requirements (Performance / Security / Compatibility)

### 4.1 Performance Requirements
- **Batch Operations**: Use batch insert/update to reduce database operations
- **Data Processing**: Use Pandas for efficient data processing
- **Status Management**: Centralized status management to avoid duplicate queries
- **Response Time**: Single block download time should not exceed 5 seconds

### 4.2 Security Requirements
- **Exception Handling**: Comprehensive exception capture and handling mechanism
- **Transaction Management**: Use database transactions to ensure data consistency
- **Error Recovery**: Support resuming downloads from breakpoints
- **Data Validation**: Validate data integrity and validity

### 4.3 Compatibility Requirements
- **Environment Compatibility**: Support different running environments (development/production)
- **API Compatibility**: Compatible with data source API interface changes
- **Database Compatibility**: Compatible with different versions of MySQL
- **Extensibility**: Support adding new task types and data sources

## 5. Business Process / Use Cases

### 5.1 Generic Download Process

**Main Download Process**:
1. **Check Status**: Get current download status
2. **Determine Status**:
   - If completed, return directly
   - If in progress, resume from breakpoint
   - If not started, set status to in progress
3. **Calculate Total Blocks**: Calculate total blocks to be downloaded
4. **Get Download Block**:
   - Priority to resume interrupted download block
   - If no interrupted block, get first pending download block
5. **Loop Download**:
   - Update download pointer
   - Download block data
   - Clean data
   - Save data
   - Get next block
   - Record progress
6. **Download Complete**:
   - Set status to completed
   - Clear download pointer
   - Return success

### 5.2 Status Transition Diagram

```
┌─────────────────┐
│  NOT_STARTED    │  ← Initial state
│  (Not Started)  │
└────────┬────────┘
         │ Call continue_*_download()
         │ Set status to IN_PROGRESS
         ↓
┌─────────────────┐
│  IN_PROGRESS    │  ← Downloading
│  (In Progress)  │
└────────┬────────┘
         │ All blocks downloaded
         │ 1. set_task_status(COMPLETED)
         │ 2. clear_download_pointer()
         ↓
┌─────────────────┐
│  COMPLETED      │  ← Download completed
│  (Completed)    │
└─────────────────┘
         ↑
         │ Call start_new_*_download()
         │ Set status to NOT_STARTED
         └───────────────────────┘
```

### 5.3 Generic Use Cases

**Use Case 1: First-time Download**
- **Trigger**: Call `start_new_*_download()`
- **Process**: Set status to not started → Call `continue_*_download()` → Set status to in progress → Download all blocks → Set status to completed
- **Expected Result**: Successfully download all data for the specified range

**Use Case 2: Breakpoint Resume**
- **Trigger**: Call `continue_*_download()` after download interruption
- **Process**: Detect status as in progress → Resume download from breakpoint → Complete remaining blocks → Set status to completed
- **Expected Result**: Resume download from breakpoint, avoid re-downloading completed blocks

**Use Case 3: Avoid Duplicate Download**
- **Trigger**: Call `continue_*_download()` after download completion
- **Process**: Detect status as completed → Return directly without executing download
- **Expected Result**: No duplicate download, improve efficiency

## 6. Data and Interfaces

### 6.1 Generic Data Structure

**Status Management Table (`global_dl_ctrl_block`)**:
| Field Name | Type | Description |
|------------|------|-------------|
| `task_type` | VARCHAR | Task type (e.g., "adjustment_factor", "xrxd") |
| `main_pointer` | VARCHAR | Primary pointer (e.g., time period) |
| `secondary_pointer` | VARCHAR | Secondary pointer (e.g., security identifier) |
| `tertiary_pointer` | VARCHAR | Tertiary pointer (optional) |
| `start_args` | VARCHAR | Start parameters (e.g., start condition, end condition) |
| `block_total` | INT | Total number of blocks |
| `block_completed` | INT | Number of completed blocks |
| `task_status` | VARCHAR | Task status (NOT_STARTED, IN_PROGRESS, COMPLETED) |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Update time |

### 6.2 Generic Interface Design

**External Interfaces**:
1. **`continue_*_download(db_conn, start_condition, end_condition)`**
   - **Function**: Continue downloading data (supports breakpoint resume)
   - **Parameters**:
     - `db_conn`: Database connection
     - `start_condition`: Start condition (inclusive)
     - `end_condition`: End condition (inclusive, default to current condition)
   - **Return**: `True` indicates all downloads completed, `False` indicates not completed

2. **`start_new_*_download(db_conn, start_condition, end_condition)`**
   - **Function**: Start a new data download task (clear previous progress)
   - **Parameters**:
     - `db_conn`: Database connection
     - `start_condition`: Start condition (inclusive)
     - `end_condition`: End condition (inclusive, default to current condition)
   - **Return**: `True` indicates all downloads completed, `False` indicates not completed

**Internal Interfaces**:
1. **`*Downloader.continue_*_download(start_condition, end_condition)`**
2. **`*Downloader.start_new_*_download(start_condition, end_condition)`**
3. **`*Manager.save_*_data(df)`**
4. **`GlobalDlCtrlBlockManager.set_*_progress(primary_condition, secondary_condition)`**
5. **`GlobalDlCtrlBlockManager.get_*_progress()`**

## 7. Acceptance Criteria

### 7.1 Functional Acceptance
- ✅ Can successfully download data from the data source API
- ✅ Can correctly clean and process data, handling null values and outliers
- ✅ Can save data to the database
- ✅ Supports breakpoint resume functionality
- ✅ Supports fresh download functionality
- ✅ Can correctly manage download status
- ✅ Can calculate and display download progress

### 7.2 Performance Acceptance
- ✅ Single block download time does not exceed 5 seconds
- ✅ Batch operations reduce database operations
- ✅ Data processing efficiency meets requirements

### 7.3 Reliability Acceptance
- ✅ Can resume download from breakpoint after network interruption
- ✅ Can rollback transactions after database operation failure
- ✅ Comprehensive exception handling mechanism
- ✅ Detailed logging

### 7.4 Maintainability Acceptance
- ✅ Clear code structure, modular design
- ✅ Complete documentation, detailed comments
- ✅ Reasonable interface design, easy to extend
- ✅ Comprehensive error handling and logging

### 7.5 Compatibility Acceptance
- ✅ Supports different running environments
- ✅ Compatible with data source API interface changes
- ✅ Compatible with different versions of MySQL
- ✅ Strong extensibility, supports adding new task types and data sources

## 8. Summary

The generic downloader framework is an important infrastructure of the Campsis platform. Through unified download process, status management, and data processing mechanisms, it ensures the reliability, efficiency, and maintainability of data acquisition. This framework not only supports the current adjustment factor and XRXD modules but also provides a good foundation for adding new data types in the future.

By implementing this generic framework, the Campsis platform can more efficiently obtain and manage various financial data, providing more comprehensive and accurate data support for business decisions. At the same time, the design ideas and implementation methods of this framework can also serve as a reference for other similar data acquisition systems.