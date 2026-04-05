# Unified KLine Downloader Design Document

## 1. Project Overview and Objectives

### 1.1 Project Overview
The Unified KLine Downloader is a core component of the Campsis platform, responsible for retrieving stock K-line data from the Baostock API and storing it in the local database. This component adopts a modular design, supporting the download, cleaning, and storage of K-line data for multiple time periods, with features such as breakpoint resume and listing time validation.

### 1.2 Project Objectives
- **Data Acquisition**: Reliably obtain stock K-line data from the Baostock API
- **Multi-period Support**: Support K-line data for different time periods (e.g., 5-minute, 15-minute, daily, etc.)
- **Efficient Download**: Download data in quarterly blocks to improve efficiency and reliability
- **Breakpoint Resume**: Support resuming downloads from interruption points to avoid duplicate downloads
- **Data Quality**: Clean and validate data to ensure data quality
- **Unified Storage**: Store processed data in a unified K-line data table

## 2. Overall Architecture Design

### 2.1 Architecture Layers
```
┌─────────────────────────────────────────────────────────┐
│                     Application Layer                  │
├─────────────────────────────────────────────────────────┤
│ main.py                                                │
│ - Main entry point, calls the downloader                │
├─────────────────────────────────────────────────────────┤
│                     Download Layer                     │
├─────────────────────────────────────────────────────────┤
│ Ingredient/kline_unified_downloader.py                 │
│ - KLineDownloader class: Core download logic           │
├─────────────────────────────────────────────────────────┤
│                   Data Management Layer                │
├─────────────────────────────────────────────────────────┤
│ Ingredient/DataNest/                                   │
│ - dm_unified.py: Unified data management               │
│ - dm_kline.py: K-line data management                 │
├─────────────────────────────────────────────────────────┤
│                    Utility Layer                       │
├─────────────────────────────────────────────────────────┤
│ KitchenBase/                                           │
│ - logger_config.py: Logging configuration              │
│ - baostock_wrapper.py: Baostock API wrapper            │
│ - stock_enums.py: Stock-related enums                  │
├─────────────────────────────────────────────────────────┤
│                    Storage Layer                       │
├─────────────────────────────────────────────────────────┤
│ MySQL Database                                         │
│ - kline_unified: K-line data storage                   │
│ - kline_block_status: Block status management          │
│ - global_dl_ctrl_block: Task status management         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Design Principles
- **Modularity**: Clear module division with well-defined responsibilities
- **Extensibility**: Support for adding new K-line periods and data sources
- **Reliability**: Breakpoint resume and error handling mechanisms
- **Performance Optimization**: Quarterly block download and batch operations

## 3. Module Division and Responsibilities

| Module | Responsibility | Core Functions |
|--------|---------------|---------------|
| **KLineDownloader** | Core download logic | Calculate total blocks, get next block, download single block, data cleaning |
| **UnifiedDataManager** | Unified data management | Save K-line data, manage block status, get download progress |
| **KLineUnifiedQuarterlyExtendedManager** | K-line data management | Specific K-line data storage implementation |
| **BaostockWrapper** | API wrapper | Convert K-line periods, call Baostock API |
| **GlobalDlCtrlBlockManager** | Task status management | Manage task-level status and progress |

## 4. Core Business Process

### 4.1 Main Download Process
1. **Initialization**: Create KLineDownloader instance
2. **Calculate Total Blocks**: Based on year range, quarter count, and stock count
3. **Get Download Block**: Priority to resume interrupted block, get first block if no interruption
4. **Loop Download**:
   - Update download pointer
   - Convert quarter to date range
   - Validate listing time
   - Call Baostock API to download data
   - Clean data
   - Save data
   - Update block status
   - Get next block
   - Record progress
5. **Complete Download**: All blocks downloaded

### 4.2 Single Block Download Process
1. **Parameter Validation**: Validate quarter and stock code
2. **Status Check**: Check if block is already completed
3. **Listing Time Validation**: Verify if stock was listed within the specified time range
4. **Download Data**: Call Baostock API to get raw data
5. **Clean Data**: Process price, volume, and other fields
6. **Save Data**: Store data in database
7. **Update Status**: Update block status to completed

## 5. Database and Data Structure Design

### 5.1 Core Data Tables

**`kline_unified` Table**:
| Field Name | Type | Description |
|------------|------|-------------|
| `std_stock_code` | VARCHAR(20) | Stock code |
| `timestamp` | DATETIME | Timestamp |
| `open_price` | DECIMAL(10,2) | Opening price |
| `high_price` | DECIMAL(10,2) | Highest price |
| `low_price` | DECIMAL(10,2) | Lowest price |
| `close_price` | DECIMAL(10,2) | Closing price |
| `volume` | BIGINT | Trading volume |
| `turnover` | DECIMAL(15,2) | Turnover |
| `time_frame` | VARCHAR(10) | K-line period |
| **PRIMARY KEY** | | (`std_stock_code`, `timestamp`, `time_frame`) |

**`kline_block_status` Table**:
| Field Name | Type | Description |
|------------|------|-------------|
| `quarter` | VARCHAR(10) | Quarter (e.g., "2024-Q1") |
| `std_stock_code` | VARCHAR(20) | Stock code |
| `time_frame` | VARCHAR(10) | K-line period |
| `status` | VARCHAR(10) | Status (pending/completed) |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Update time |
| **PRIMARY KEY** | | (`quarter`, `std_stock_code`, `time_frame`) |

**`global_dl_ctrl_block` Table**:
| Field Name | Type | Description |
|------------|------|-------------|
| `task_type` | VARCHAR(50) | Task type (e.g., "kline") |
| `main_pointer` | VARCHAR(50) | Main pointer (e.g., quarter) |
| `secondary_pointer` | VARCHAR(50) | Secondary pointer (e.g., stock code) |
| `tertiary_pointer` | VARCHAR(50) | Tertiary pointer (e.g., K-line period) |
| `start_args` | VARCHAR(255) | Start parameters |
| `block_total` | INT | Total number of blocks |
| `block_completed` | INT | Number of completed blocks |
| `task_status` | VARCHAR(20) | Task status |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Update time |
| **PRIMARY KEY** | | (`task_type`) |

### 5.2 Data Structures

**KLinePeriod Enum**:
- MIN_1: 1 minute
- MIN_5: 5 minutes
- MIN_15: 15 minutes
- MIN_30: 30 minutes
- MIN_60: 60 minutes
- DAY: Daily
- WEEK: Weekly
- MONTH: Monthly

**Block Definition**:
- Uniquely identified by `(quarter, stock_code, time_frame)`
- Quarter format: YYYY-QN (e.g., "2024-Q1")

## 6. Interface Design Overview

### 6.1 External Interfaces
1. **`download_kline(db_conn, start_year, end_year, time_frame)`**
   - **Function**: Download K-line data for specified time range and period
   - **Parameters**:
     - `db_conn`: Database connection
     - `start_year`: Start year (inclusive)
     - `end_year`: End year (exclusive)
     - `time_frame`: K-line period enum
   - **Return**: No return value, throws exception on error

### 6.2 Internal Interfaces
1. **`KLineDownloader.download_kline(start_year, end_year, time_frame)`**
   - **Function**: Core download logic
   - **Parameters**: Same as external interface
   - **Return**: No return value

2. **`KLineDownloader._fetch_kline_block(quarter, std_stock_code, time_frame)`**
   - **Function**: Download single block
   - **Parameters**:
     - `quarter`: Quarter
     - `std_stock_code`: Stock code
     - `time_frame`: K-line period
   - **Return**: No return value

3. **`KLineDownloader._clean_kline_data(raw_data, time_frame)`**
   - **Function**: Clean K-line data
   - **Parameters**:
     - `raw_data`: Raw data
     - `time_frame`: K-line period
   - **Return**: Cleaned data DataFrame

4. **`UnifiedDataManager.save_kline_data_unified(db_conn, std_stock_code, df)`**
   - **Function**: Save K-line data
   - **Parameters**:
     - `db_conn`: Database connection
     - `std_stock_code`: Stock code
     - `df`: K-line data DataFrame
   - **Return**: Whether save was successful

5. **`UnifiedDataManager.update_kline_block_status(db_conn, quarter, std_stock_code, time_frame, status)`**
   - **Function**: Update block status
   - **Parameters**:
     - `db_conn`: Database connection
     - `quarter`: Quarter
     - `std_stock_code`: Stock code
     - `time_frame`: K-line period
     - `status`: Status
   - **Return**: Whether update was successful

## 7. Technology Selection

| Category | Technology/Library | Purpose |
|----------|--------------------|---------|
| Programming Language | Python 3.8+ | Main development language |
| Database | MySQL 5.7+ | Data storage |
| Financial Data API | Baostock | K-line data source |
| Data Processing | Pandas | Data cleaning and processing |
| Database Connection | pymysql | MySQL connection |
| Logging | logging | Log recording |
| Type Hints | typing | Type annotations |
| Date Processing | datetime | Date and time handling |

## 8. Deployment and Runtime Environment

### 8.1 Hardware Requirements
- **CPU**: At least 2 cores
- **Memory**: At least 4GB
- **Storage**: Depending on data volume, recommended at least 100GB

### 8.2 Software Requirements
- **Operating System**: Windows/Linux/macOS
- **Python**: Version 3.8 or higher
- **MySQL**: Version 5.7 or higher
- **Dependencies**:
  - pandas
  - pymysql
  - baostock

### 8.3 Running Methods
1. **Direct Execution**:
   ```bash
   python main.py
   ```

2. **Import as Module**:
   ```python
   from Ingredient.kline_unified_downloader import download_kline
   from KitchenBase.stock_enums import KLinePeriod
   
   # Download 5-minute K-line data for 2024
   download_kline(db_conn, 2024, 2025, KLinePeriod.MIN_5)
   ```

### 8.4 Configuration Requirements
- **Database Configuration**: MySQL connection information needs to be configured
- **Baostock Login**: Need to log in to Baostock service before use
- **Logging Configuration**: Log level can be adjusted through environment variables

## 9. Summary

The Unified KLine Downloader is a well-designed, fully functional K-line data acquisition component that adopts a modular design, supporting the download, cleaning, and storage of K-line data for multiple time periods. This component features breakpoint resume, listing time validation, and other functions to ensure the reliability and efficiency of data acquisition. Through quarterly block download strategy and batch operation optimization, it improves download efficiency and system stability.

This design not only meets current K-line data acquisition needs but also reserves space for future function expansion and performance optimization, making it an important infrastructure of the Campsis platform.