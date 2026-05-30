       *================================================================*
       * COPYBOOK: COMMONERR                                            *
       * PURPOSE:  Standard error handling data definitions             *
       *================================================================*
       01 WS-ERROR-DATA.
          05 WS-ERROR-CODE         PIC 9(4)      VALUE ZEROS.
          05 WS-ERROR-MESSAGE      PIC X(80)     VALUE SPACES.
          05 WS-ERROR-PROGRAM      PIC X(8)      VALUE SPACES.
          05 WS-ERROR-PARAGRAPH    PIC X(30)     VALUE SPACES.
          05 WS-ERROR-TIMESTAMP    PIC 9(14)     VALUE ZEROS.
          05 WS-ERROR-SEVERITY     PIC X(1)      VALUE SPACES.
             88 WS-SEVERITY-INFO   VALUE 'I'.
             88 WS-SEVERITY-WARN   VALUE 'W'.
             88 WS-SEVERITY-ERROR  VALUE 'E'.
             88 WS-SEVERITY-FATAL  VALUE 'F'.
