 *================================================================*
      * PROGRAM:    MORTGAGE-CALC                                      *
      * AUTHOR:     SYSTEMS DEVELOPMENT TEAM                          *
      * DATE:       1987-03-14                                        *
      * PURPOSE:    MORTGAGE AMORTISATION CALCULATION ROUTINE         *
      *             CALCULATES MONTHLY REPAYMENTS, PRINCIPAL/INTEREST *
      *             SPLIT, EARLY REPAYMENT PENALTIES AND TOTAL COST   *
      *             OF LOAN OVER FULL TERM.                           *
      *----------------------------------------------------------------*
      * CHANGE LOG:                                                    *
      * 1987-03-14  INITIAL VERSION                                   *
      * 1992-11-02  ADDED EARLY REPAYMENT PENALTY LOGIC               *
      * 1998-06-15  UPDATED ROUNDING TO COMPLY WITH FSA RULES        *
      * 2003-09-30  ADDED VARIABLE RATE SUPPORT                       *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MORTGAGE-CALC.
 
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-MAINFRAME.
       OBJECT-COMPUTER. IBM-MAINFRAME.
 
       DATA DIVISION.
       WORKING-STORAGE SECTION.
 
      *----------------------------------------------------------------*
      * INPUT FIELDS                                                   *
      *----------------------------------------------------------------*
       01 WS-INPUT.
          05 WS-PRINCIPAL          PIC 9(10)V99 VALUE ZEROS.
          05 WS-ANNUAL-RATE        PIC 9(3)V9(6) VALUE ZEROS.
          05 WS-TERM-YEARS         PIC 9(3)     VALUE ZEROS.
          05 WS-REPAYMENT-MONTH    PIC 9(4)     VALUE ZEROS.
          05 WS-RATE-TYPE          PIC X        VALUE 'F'.
             88 FIXED-RATE         VALUE 'F'.
             88 VARIABLE-RATE      VALUE 'V'.
 
      *----------------------------------------------------------------*
      * CALCULATED FIELDS                                              *
      *----------------------------------------------------------------*
       01 WS-CALCULATIONS.
          05 WS-MONTHLY-RATE       PIC 9(3)V9(10) VALUE ZEROS.
          05 WS-TERM-MONTHS        PIC 9(5)       VALUE ZEROS.
          05 WS-MONTHLY-PAYMENT    PIC 9(10)V99   VALUE ZEROS.
          05 WS-TOTAL-REPAYABLE    PIC 9(12)V99   VALUE ZEROS.
          05 WS-TOTAL-INTEREST     PIC 9(12)V99   VALUE ZEROS.
          05 WS-CURRENT-BALANCE    PIC 9(10)V99   VALUE ZEROS.
          05 WS-INTEREST-PORTION   PIC 9(10)V99   VALUE ZEROS.
          05 WS-PRINCIPAL-PORTION  PIC 9(10)V99   VALUE ZEROS.
          05 WS-PENALTY-AMOUNT     PIC 9(10)V99   VALUE ZEROS.
          05 WS-MONTHS-REMAINING   PIC 9(5)       VALUE ZEROS.
 
      *----------------------------------------------------------------*
      * INTERMEDIATE CALCULATION FIELDS                                *
      *----------------------------------------------------------------*
       01 WS-INTERMEDIATE.
          05 WS-RATE-PLUS-ONE      PIC 9(3)V9(10) VALUE ZEROS.
          05 WS-COMPOUND-FACTOR    PIC 9(10)V9(10) VALUE ZEROS.
          05 WS-COMPOUND-MINUS-ONE PIC 9(10)V9(10) VALUE ZEROS.
          05 WS-NUMERATOR          PIC 9(15)V9(10) VALUE ZEROS.
          05 WS-LOOP-COUNTER       PIC 9(5)        VALUE ZEROS.
          05 WS-TEMP-CALC          PIC 9(15)V9(10) VALUE ZEROS.
          05 WS-PENALTY-RATE       PIC 9(3)V9(6)   VALUE ZEROS.
          05 WS-PENALTY-MONTHS     PIC 9(3)        VALUE ZEROS.
 
      *----------------------------------------------------------------*
      * OUTPUT FIELDS                                                  *
      *----------------------------------------------------------------*
       01 WS-OUTPUT.
          05 WS-OUT-MONTHLY-PMT    PIC 9(10)V99   VALUE ZEROS.
          05 WS-OUT-TOTAL-COST     PIC 9(12)V99   VALUE ZEROS.
          05 WS-OUT-TOTAL-INT      PIC 9(12)V99   VALUE ZEROS.
          05 WS-OUT-MONTH-INT      PIC 9(10)V99   VALUE ZEROS.
          05 WS-OUT-MONTH-PRIN     PIC 9(10)V99   VALUE ZEROS.
          05 WS-OUT-BALANCE        PIC 9(10)V99   VALUE ZEROS.
          05 WS-OUT-PENALTY        PIC 9(10)V99   VALUE ZEROS.
          05 WS-OUT-RETURN-CODE    PIC 9(2)        VALUE ZEROS.
             88 CALC-SUCCESS       VALUE 00.
             88 INVALID-PRINCIPAL  VALUE 01.
             88 INVALID-RATE       VALUE 02.
             88 INVALID-TERM       VALUE 03.
             88 INVALID-MONTH      VALUE 04.
 
      *----------------------------------------------------------------*
      * CONSTANTS                                                      *
      *----------------------------------------------------------------*
       01 WS-CONSTANTS.
          05 WS-MONTHS-IN-YEAR     PIC 9(2)       VALUE 12.
          05 WS-PENALTY-THRESHOLD  PIC 9(2)       VALUE 36.
          05 WS-EARLY-PENALTY-PCT  PIC 9(3)V9(6)  VALUE 0.030000.
          05 WS-ROUNDING-FACTOR    PIC 9(3)V99    VALUE 0.01.
 
       PROCEDURE DIVISION.
 
      *================================================================*
       MAIN-PROCEDURE.
      *================================================================*
           PERFORM VALIDATE-INPUTS
           IF CALC-SUCCESS
               PERFORM CALCULATE-MONTHLY-RATE
               PERFORM CALCULATE-TERM-MONTHS
               PERFORM CALCULATE-MONTHLY-PAYMENT
               PERFORM CALCULATE-MONTH-BREAKDOWN
               PERFORM CALCULATE-TOTALS
               PERFORM CALCULATE-PENALTY
               PERFORM POPULATE-OUTPUT
           END-IF
           STOP RUN.
 
      *================================================================*
       VALIDATE-INPUTS.
      *================================================================*
           MOVE 00 TO WS-OUT-RETURN-CODE
 
           IF WS-PRINCIPAL <= ZEROS OR WS-PRINCIPAL > 9999999.99
               MOVE 01 TO WS-OUT-RETURN-CODE
               GO TO VALIDATE-INPUTS-EXIT
           END-IF
 
           IF WS-ANNUAL-RATE <= ZEROS OR WS-ANNUAL-RATE > 99.999999
               MOVE 02 TO WS-OUT-RETURN-CODE
               GO TO VALIDATE-INPUTS-EXIT
           END-IF
 
           IF WS-TERM-YEARS <= ZEROS OR WS-TERM-YEARS > 40
               MOVE 03 TO WS-OUT-RETURN-CODE
               GO TO VALIDATE-INPUTS-EXIT
           END-IF
 
           IF WS-REPAYMENT-MONTH <= ZEROS OR
              WS-REPAYMENT-MONTH > (WS-TERM-YEARS * WS-MONTHS-IN-YEAR)
               MOVE 04 TO WS-OUT-RETURN-CODE
               GO TO VALIDATE-INPUTS-EXIT
           END-IF
 
       VALIDATE-INPUTS-EXIT.
           EXIT.
 
      *================================================================*
       CALCULATE-MONTHLY-RATE.
      *================================================================*
      * DIVIDE ANNUAL RATE BY 12 TO GET MONTHLY RATE                  *
      * RATE IS STORED AS DECIMAL E.G. 5.25% = 0.0525                 *
      *================================================================*
           DIVIDE WS-ANNUAL-RATE BY WS-MONTHS-IN-YEAR
               GIVING WS-MONTHLY-RATE
               ROUNDED.
 
      *================================================================*
       CALCULATE-TERM-MONTHS.
      *================================================================*
           MULTIPLY WS-TERM-YEARS BY WS-MONTHS-IN-YEAR
               GIVING WS-TERM-MONTHS.
 
      *================================================================*
       CALCULATE-MONTHLY-PAYMENT.
      *================================================================*
      * STANDARD AMORTISATION FORMULA:                                 *
      *   M = P * [r(1+r)^n] / [(1+r)^n - 1]                        *
      *   WHERE:                                                       *
      *     M = MONTHLY PAYMENT                                        *
      *     P = PRINCIPAL                                              *
      *     r = MONTHLY INTEREST RATE                                  *
      *     n = NUMBER OF PAYMENTS (MONTHS)                            *
      *================================================================*
           ADD 1 TO WS-MONTHLY-RATE GIVING WS-RATE-PLUS-ONE
 
      * CALCULATE (1+r)^n USING LOOP - MAINFRAME COMPATIBLE           *
           MOVE 1 TO WS-COMPOUND-FACTOR
           MOVE 0 TO WS-LOOP-COUNTER
 
           PERFORM UNTIL WS-LOOP-COUNTER >= WS-TERM-MONTHS
               MULTIPLY WS-COMPOUND-FACTOR BY WS-RATE-PLUS-ONE
                   GIVING WS-COMPOUND-FACTOR ROUNDED
               ADD 1 TO WS-LOOP-COUNTER
           END-PERFORM
 
      * CALCULATE NUMERATOR: P * r * (1+r)^n                          *
           MULTIPLY WS-PRINCIPAL BY WS-MONTHLY-RATE
               GIVING WS-TEMP-CALC ROUNDED
           MULTIPLY WS-TEMP-CALC BY WS-COMPOUND-FACTOR
               GIVING WS-NUMERATOR ROUNDED
 
      * CALCULATE DENOMINATOR: (1+r)^n - 1                            *
           SUBTRACT 1 FROM WS-COMPOUND-FACTOR
               GIVING WS-COMPOUND-MINUS-ONE
 
      * MONTHLY PAYMENT = NUMERATOR / DENOMINATOR                     *
           DIVIDE WS-NUMERATOR BY WS-COMPOUND-MINUS-ONE
               GIVING WS-MONTHLY-PAYMENT ROUNDED.
 
      *================================================================*
       CALCULATE-MONTH-BREAKDOWN.
      *================================================================*
      * CALCULATE THE PRINCIPAL/INTEREST SPLIT FOR A GIVEN MONTH      *
      * FIRST DERIVE THE BALANCE AT THE START OF THAT MONTH           *
      *================================================================*
           MOVE WS-PRINCIPAL TO WS-CURRENT-BALANCE
           MOVE 0 TO WS-LOOP-COUNTER
 
           PERFORM UNTIL
               WS-LOOP-COUNTER >= (WS-REPAYMENT-MONTH - 1)
 
      * INTEREST FOR THIS MONTH                                        *
               MULTIPLY WS-CURRENT-BALANCE BY WS-MONTHLY-RATE
                   GIVING WS-INTEREST-PORTION ROUNDED
 
      * PRINCIPAL FOR THIS MONTH                                       *
               SUBTRACT WS-INTEREST-PORTION FROM WS-MONTHLY-PAYMENT
                   GIVING WS-PRINCIPAL-PORTION
 
      * REDUCE BALANCE                                                 *
               SUBTRACT WS-PRINCIPAL-PORTION FROM WS-CURRENT-BALANCE
 
               ADD 1 TO WS-LOOP-COUNTER
           END-PERFORM
 
      * NOW CALCULATE FOR THE REQUESTED MONTH                          *
           MULTIPLY WS-CURRENT-BALANCE BY WS-MONTHLY-RATE
               GIVING WS-INTEREST-PORTION ROUNDED
 
           SUBTRACT WS-INTEREST-PORTION FROM WS-MONTHLY-PAYMENT
               GIVING WS-PRINCIPAL-PORTION
 
           SUBTRACT WS-PRINCIPAL-PORTION FROM WS-CURRENT-BALANCE
               GIVING WS-OUT-BALANCE.
 
      *================================================================*
       CALCULATE-TOTALS.
      *================================================================*
           MULTIPLY WS-MONTHLY-PAYMENT BY WS-TERM-MONTHS
               GIVING WS-TOTAL-REPAYABLE ROUNDED
 
           SUBTRACT WS-PRINCIPAL FROM WS-TOTAL-REPAYABLE
               GIVING WS-TOTAL-INTEREST.
 
      *================================================================*
       CALCULATE-PENALTY.
      *================================================================*
      * EARLY REPAYMENT PENALTY APPLIES IF:                            *
      *   - REPAYMENT IS WITHIN FIRST 36 MONTHS (3 YEARS)             *
      *   - RATE TYPE IS FIXED                                         *
      * PENALTY = 3% OF OUTSTANDING BALANCE AT TIME OF REPAYMENT      *
      *================================================================*
           MOVE ZEROS TO WS-PENALTY-AMOUNT
 
           IF FIXED-RATE AND
              WS-REPAYMENT-MONTH <= WS-PENALTY-THRESHOLD
 
               MULTIPLY WS-OUT-BALANCE BY WS-EARLY-PENALTY-PCT
                   GIVING WS-PENALTY-AMOUNT ROUNDED
 
           END-IF.
 
      *================================================================*
       POPULATE-OUTPUT.
      *================================================================*
           MOVE WS-MONTHLY-PAYMENT  TO WS-OUT-MONTHLY-PMT
           MOVE WS-TOTAL-REPAYABLE  TO WS-OUT-TOTAL-COST
           MOVE WS-TOTAL-INTEREST   TO WS-OUT-TOTAL-INT
           MOVE WS-INTEREST-PORTION TO WS-OUT-MONTH-INT
           MOVE WS-PRINCIPAL-PORTION TO WS-OUT-MONTH-PRIN
           MOVE WS-PENALTY-AMOUNT   TO WS-OUT-PENALTY.
 
      *================================================================*
      * END OF PROGRAM MORTGAGE-CALC                                   *
      *================================================================*
