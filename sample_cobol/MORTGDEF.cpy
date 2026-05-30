       *================================================================*
       * COPYBOOK: MORTGDEF                                             *
       * PURPOSE:  Shared mortgage data definitions                     *
       *           Used by MORTGAGE-CALC and related programs           *
       *================================================================*
       01 MORTGAGE-COMMON-DATA.
          05 MC-CUSTOMER-ID        PIC 9(10)     VALUE ZEROS.
          05 MC-PRODUCT-CODE       PIC X(8)      VALUE SPACES.
          05 MC-PRODUCT-DESC       PIC X(40)     VALUE SPACES.
          05 MC-ORIGINATION-DATE   PIC 9(8)      VALUE ZEROS.
          05 MC-ORIGINATION-DATE   PIC 9(8)      VALUE ZEROS.
          05 MC-CURRENCY-CODE      PIC X(3)      VALUE 'GBP'.
          05 MC-STATUS-CODE        PIC X(2)      VALUE SPACES.
             88 MC-ACTIVE          VALUE 'AC'.
             88 MC-CLOSED          VALUE 'CL'.
             88 MC-ARREARS         VALUE 'AR'.
             88 MC-WRITTEN-OFF     VALUE 'WO'.
          05 MC-BRANCH-CODE        PIC 9(4)      VALUE ZEROS.
          05 MC-OFFICER-ID         PIC X(8)      VALUE SPACES.

       01 MORTGAGE-AUDIT-DATA.
          05 MA-CREATED-BY         PIC X(8)      VALUE SPACES.
          05 MA-CREATED-DATE       PIC 9(8)      VALUE ZEROS.
          05 MA-LAST-MODIFIED-BY   PIC X(8)      VALUE SPACES.
          05 MA-LAST-MODIFIED-DATE PIC 9(8)      VALUE ZEROS.
          05 MA-VERSION-NUMBER     PIC 9(4)      VALUE ZEROS.
          05 MA-CHANGE-REASON      PIC X(80)     VALUE SPACES.
