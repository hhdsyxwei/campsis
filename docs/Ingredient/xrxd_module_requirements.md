# XRXD Module Requirements Document

## 1. Project Background and Objectives

### 1.1 Project Background
Campsis is an enterprise-grade data intelligence platform aimed at empowering business decisions through data. To achieve this goal, the platform needs to obtain various financial data from multiple data sources, including stock dividend and bonus data.

### 1.2 Project Objectives
The objectives of the XRXD module are:
- Reliably obtain stock dividend and bonus data from the Baostock API
- Clean and process data to ensure data quality
- Store processed data in the database for use by other platform modules
- Support breakpoint resume and fresh download functions to improve download reliability
- Provide a clear state management mechanism for monitoring and maintenance

## 2. Basic Concept Definitions

| Concept | Definition | Description |
|---------|------------|-------------|
| **Task** | Represents a collection of download blocks within a specific range | Typically corresponds to a complete download operation, containing multiple blocks across different years and stocks |
| **Block** | Represents data for one stock in one year | Uniquely identified by (year, stock_code), the minimum download unit |
| **Pointer** | Used to track current download progress | Contains primary pointer (year), secondary pointer (stock code), and tertiary pointer (empty) |
| **Download Status** | Current status of the task | Includes: Not Started, In Progress, Completed |

## 3. Functional Requirements (What to Do)

### 3.1 Core Functions
1. **Data Download**: Obtain raw dividend and bonus data from the Baostock API
2. **Data Cleaning**: Handle null values, outliers, and convert data formats
3. **Data Storage**: Save cleaned data to the `stock_xrxd` table
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
- **API Compatibility**: Compatible with Baostock API interface changes
- **Database Compatibility**: Compatible with different versions of MySQL
- **Extensibility**: Support adding new task types and data sources

## 5. Business Process / Use Cases

### 5.1 Download Process

**Main Download Process**:
1. **Check Status**: Call `_get_download_status()` to get current download status
2. **Determine Status**:
   - If completed, return directly
   - If in progress, resume from breakpoint
   - If not started, set status to in progress
3. **Calculate Total Blocks**: Call `_calc_total_blocks()` to calculate total blocks
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
   - Clear download pointer
   - Set status to completed
   - Return success

### 5.2 Status Transition Diagram

```
┌─────────────────┐
│  NOT_STARTED    │  ← Initial state
│  (Not Started)  │
└────────┬────────┘
         │ Call continue_download_xrxd()
         │ Set status to IN_PROGRESS
         ↓
┌─────────────────┐
│  IN_PROGRESS    │  ← Downloading
│  (In Progress)  │
└────────┬────────┘
         │ All blocks downloaded
         │ 1. clear_download_pointer()
         │ 2. set_task_status(COMPLETED)
         ↓
┌─────────────────┐
│  COMPLETED      │  ← Download completed
│  (Completed)    │
└─────────────────┘
         ↑
         │ Call start_new_xrxd_download()
         │ Set status to NOT_STARTED
         └───────────────────────┘
```

### 5.3 Use Cases

**Use Case 1: First-time Download**
- **Trigger**: Call `start_new_xrxd_download()`
- **Process**: Set status to not started → Call `continue_download_xrxd()` → Set status to in progress → Download all blocks → Set status to completed
- **Expected Result**: Successfully download all dividend and bonus data for the specified year range

**Use Case 2: Breakpoint Resume**
- **Trigger**: Call `continue_download_xrxd()` after download interruption
- **Process**: Detect status as in progress → Resume download from breakpoint → Complete remaining blocks → Set status to completed
- **Expected Result**: Resume download from breakpoint, avoid re-downloading completed blocks

**Use Case 3: Avoid Duplicate Download**
- **Trigger**: Call `continue_download_xrxd()` after download completion
- **Process**: Detect status as completed → Return directly without executing download
- **Expected Result**: No duplicate download, improve efficiency

## 6. Data and Interfaces

### 6.1 Data Structure

**`stock_xrxd` Table Structure**:
| Field Name | Type | Description |
|------------|------|-------------|
| `std_stock_code` | VARCHAR | Stock code |
| `xrxd_year` | INT | Dividend and bonus year |
| `xrxd_pre_notice_date` | DATE | Pre-announcement date |
| `xrxd_agm_pum_date` | DATE | AGM announcement date |
| `xrxd_plan_announce_date` | DATE | Plan announcement date |
| `xrxd_plan_date` | DATE | Plan date |
| `xrxd_regist_date` | DATE | Registration date |
| `xrxd_operate_date` | DATE | Ex-dividend date |
| `xrxd_pay_date` | DATE | Payment date |
| `xrxd_stock_market_date` | DATE | Stock listing date |
| `xrxd_cash_ps_before_tax` | DECIMAL | Cash dividend per share (before tax) |
| `xrxd_cash_ps_after_tax` | DECIMAL | Cash dividend per share (after tax) |
| `xrxd_stocks_ps` | DECIMAL | Stock dividend per share |
| `xrxd_cash_stock` | VARCHAR | Capitalization per share |
| `xrxd_reserve_to_stock_ps` | DECIMAL | Capital reserve to stock per share |

### 6.2 Core Interfaces

**External Interfaces**:
1. **`continue_download_xrxd(db_conn, start_year, end_year)`**
   - **Function**: Continue downloading dividend and bonus data (supports breakpoint resume)
   - **Parameters**:
     - `db_conn`: Database connection
     - `start_year`: Start year (inclusive)
     - `end_year`: End year (inclusive)
   - **Return**: `True` indicates all downloads completed, `False` indicates not completed

2. **`start_new_xrxd_download(db_conn, start_year, end_year)`**
   - **Function**: Start a new dividend and bonus data download task (clear previous progress)
   - **Parameters**:
     - `db_conn`: Database connection
     - `start_year`: Start year (inclusive)
     - `end_year`: End year (inclusive)
   - **Return**: `True` indicates all downloads completed, `False` indicates not completed

**Internal Interfaces**:
1. **`XrxdDownloader.continue_download_xrxd(start_year, end_year)`**
2. **`XrxdDownloader.start_new_xrxd_download(start_year, end_year)`**
3. **`XrxdManager.save_xrxd_data(df)`**
4. **`GlobalDlCtrlBlockManager.set_xrxd_progress(year, stock_code)`**
5. **`GlobalDlCtrlBlockManager.get_xrxd_progress()`**

## 7. Acceptance Criteria

### 7.1 Functional Acceptance
- ✅ Can successfully download dividend and bonus data from Baostock API
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
- ✅ Compatible with Baostock API interface changes
- ✅ Compatible with different versions of MySQL
- ✅ Strong extensibility, supports adding new task types and data sources

## 8. Summary

The XRXD download module is an important component of the Campsis platform, responsible for obtaining stock dividend and bonus data from the Baostock API and storing it in the database. The module is well-designed, fully functional, and supports core features such as breakpoint resume and fresh download, with good performance, reliability, and extensibility.

By implementing this module, the Campsis platform can obtain complete stock dividend and bonus data, providing more comprehensive data support for business decisions. At the same time, the design ideas and implementation methods of this module can also serve as a reference for other similar data download modules.