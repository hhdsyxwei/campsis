# XRXD Module Requirements Document

## 1. Project Background and Objectives

### 1.1 Project Background

Campsis is an enterprise-grade data intelligence platform aimed at empowering business decisions through data. To achieve this goal, the platform needs to obtain various financial data from multiple data sources, including stock dividend and bonus data.

1.2 Project Objectives

The objectives of the XRXD module are:

- Reliably obtain stock dividend and bonus data from the Baostock API
- Clean and process data to ensure data quality
- Store processed data in the database for use by other platform modules
- Support breakpoint resume and fresh download functions to improve download reliability
- Provide a clear state management mechanism for monitoring and maintenance

## 2. Basic Concept Definitions

### 2.1 General Concepts

For general concepts such as Block, Task, Pointer, and Download Status, please refer to the [Generic Downloader Requirements Document](downloader_generic_requirements.md).

### 2.2 XRXD-Specific Concepts

| Concept              | Definition                                                            | Description                                                                 |
| -------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **XRXD Data**        | Dividend and bonus data of stocks                                     | Includes cash dividends, stock dividends, capitalization, and related dates |
| **XRXD Year**        | The year in which the dividend and bonus event occurs                 | Typically corresponds to the fiscal year of the company                     |
| **Ex-dividend Date** | The date on which the stock starts trading without the dividend value | Important for calculating adjusted stock prices                             |

## 3. Functional Requirements (What to Do)

### 3.1 General Functions

For general functions such as Data Download, Data Cleaning, Data Storage, Breakpoint Resume, and Fresh Download, please refer to the [Generic Downloader Requirements Document](downloader_generic_requirements.md).

### 3.2 XRXD-Specific Functions

1. **Dividend and Bonus Data Acquisition**: Specifically download dividend and bonus data from Baostock API using `query_dividend_data` function
2. **Year-based Data Collection**: Collect data on a yearly basis with support for both "report" and "operate" year types
3. **XRXD-specific Data Cleaning**: Handle XRXD-specific data fields such as dividend dates, cash amounts, and stock dividend ratios
4. **XRXD Data Validation**: Validate the integrity and consistency of dividend and bonus data
5. **Dividend Date Processing**: Special handling for various dividend-related dates (pre-announcement, AGM, registration, etc.)

## 4. Non-Functional Requirements (Performance / Security / Compatibility)

### 4.1 General Requirements

For general non-functional requirements, please refer to the [Generic Downloader Requirements Document](downloader_generic_requirements.md).

### 4.2 XRXD-Specific Requirements

- **Data Accuracy**: Ensure the accuracy of dividend and bonus data, especially for critical dates and amounts
- **API Parameter Handling**: Properly handle Baostock API parameters specific to dividend data (e.g., yearType)
- **Date Validation**: Validate the logical sequence of dividend-related dates
- **Amount Precision**: Maintain proper precision for dividend amounts and ratios

## 5. Business Process / Use Cases

### 5.1 General Process

For the general download process and status transition, please refer to the [Generic Downloader Requirements Document](downloader_generic_requirements.md).

### 5.2 XRXD-Specific Process

**XRXD Download Process**:

1. **Check Status**: Same as general process (refer to generic document)
2. **Determine Status**: Same as general process (refer to generic document)
3. **Calculate Total Blocks**: Calculate based on year range and stock count
4. **Get Download Block**: Priority to resume interrupted block
5. **Loop Download**:
   - Update download pointer
   - **Call Baostock API with yearType parameter** ("report" or "operate")
   - **Clean XRXD-specific data fields** (dates, amounts, ratios)
   - **Validate dividend date sequence** (pre-announcement < AGM < registration < ex-dividend < payment)
   - Save data to `stock_xrxd` table
   - Get next block
   - Record progress
6. **Download Complete**: Set status to completed and clear pointer

### 5.3 XRXD-Specific Use Cases

**Use Case 1: Download by Report Year**

- **Trigger**: Call `continue_download_xrxd()` with specific year range
- **Process**: Download data using `yearType="report"` to get data based on fiscal year
- **Expected Result**: Successfully download dividend and bonus data based on company reporting periods

**Use Case 2: Download by Operate Year**

- **Trigger**: Call `continue_download_xrxd()` with specific year range
- **Process**: Download data using `yearType="operate"` to get data based on actual operation dates
- **Expected Result**: Successfully download dividend and bonus data based on actual ex-dividend dates

## 6. Data and Interfaces

### 6.1 XRXD-Specific Data Structure

**`stock_xrxd`** **Table Structure**:

| Field Name                 | Type    | Description                          |
| -------------------------- | ------- | ------------------------------------ |
| `std_stock_code`           | VARCHAR | Stock code                           |
| `xrxd_year`                | INT     | Dividend and bonus year              |
| `xrxd_pre_notice_date`     | DATE    | Pre-announcement date                |
| `xrxd_agm_pum_date`        | DATE    | AGM announcement date                |
| `xrxd_plan_announce_date`  | DATE    | Plan announcement date               |
| `xrxd_plan_date`           | DATE    | Plan date                            |
| `xrxd_regist_date`         | DATE    | Registration date                    |
| `xrxd_operate_date`        | DATE    | Ex-dividend date                     |
| `xrxd_pay_date`            | DATE    | Payment date                         |
| `xrxd_stock_market_date`   | DATE    | Stock listing date                   |
| `xrxd_cash_ps_before_tax`  | DECIMAL | Cash dividend per share (before tax) |
| `xrxd_cash_ps_after_tax`   | DECIMAL | Cash dividend per share (after tax)  |
| `xrxd_stocks_ps`           | DECIMAL | Stock dividend per share             |
| `xrxd_cash_stock`          | VARCHAR | Capitalization per share             |
| `xrxd_reserve_to_stock_ps` | DECIMAL | Capital reserve to stock per share   |

### 6.2 XRXD-Specific Interfaces

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

1. **`XrxdDownloader._download_raw_xrxd_data(stock_code, year)`**
   - **Function**: Download raw dividend and bonus data from Baostock API
   - **Parameters**:
     - `stock_code`: Stock code
     - `year`: Year
   - **Return**: Raw data DataFrame or None
2. **`XrxdDownloader._clean_xrxd_data(raw_df, stock_code, year)`**
   - **Function**: Clean and process XRXD data
   - **Parameters**:
     - `raw_df`: Raw data DataFrame
     - `stock_code`: Stock code
     - `year`: Year
   - **Return**: Cleaned data DataFrame or None
3. **`XrxdManager.save_xrxd_data(df)`**
   - **Function**: Save XRXD data to database
   - **Parameters**:
     - `df`: XRXD data DataFrame
   - **Return**: Boolean indicating success

## 7. Acceptance Criteria

### 7.1 General Criteria

For general acceptance criteria, please refer to the [Generic Downloader Requirements Document](downloader_generic_requirements.md).

### 7.2 XRXD-Specific Criteria

- ✅ Can successfully download dividend and bonus data for all stocks in the specified year range
- ✅ Can correctly handle different types of dividend events (cash dividends, stock dividends, capitalization)
- ✅ Can properly validate and process dividend-related dates
- ✅ Can maintain data consistency even with missing or partial data
- ✅ Can handle edge cases such as stocks with no dividend history
- ✅ Data accuracy verified against official company announcements

## 8. Summary

The XRXD download module is a specialized component of the Campsis platform, focused on obtaining and processing stock dividend and bonus data from the Baostock API. While following the general downloader framework, it includes specific functionality for handling the unique aspects of dividend and bonus data, such as multiple date fields, different dividend types, and year-based data collection.

By implementing this specialized module, the Campsis platform can provide comprehensive dividend and bonus data for investment analysis, portfolio management, and financial modeling. The module's design ensures reliable data acquisition, proper data validation, and efficient processing, making it a valuable component of the overall data intelligence platform.
