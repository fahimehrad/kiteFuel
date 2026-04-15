// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/KiteFuelEscrow.sol";

contract KiteFuelEscrowTest is Test {
    KiteFuelEscrow public escrow;

    address public authorizedSigner = address(0x1);
    address public borrower         = address(0x2);
    address public lender           = address(0x3);
    address public attacker         = address(0x4);

    bytes32 public constant TASK_ID = keccak256("task-001");

    // Amounts are denominated in KITE (Kite Chain native token). 1 ether == 1 KITE in wei notation.
    uint256 public constant CREDIT_AMOUNT = 1 ether;   // 1 KITE
    uint256 public constant REPAY_AMOUNT  = 1.1 ether; // 1.1 KITE (10 % premium)

    function setUp() public {
        escrow = new KiteFuelEscrow(authorizedSigner);

        deal(lender,   10 ether); // 10 KITE
        deal(borrower, 10 ether); // 10 KITE
        deal(attacker, 10 ether); // 10 KITE
    }

    // Invariant: full lifecycle (fund → spend → revenue > repay → settle) distributes KITE correctly
    function test_HappyPath() public {
        uint256 revenue = 1.5 ether; // 1.5 KITE — exceeds repayAmount, so borrower gets remainder

        escrow.createTaskEscrow(TASK_ID, borrower, lender, CREDIT_AMOUNT, REPAY_AMOUNT);

        vm.prank(lender);
        escrow.fundCredit{value: CREDIT_AMOUNT}(TASK_ID);

        vm.prank(authorizedSigner);
        escrow.markSpend(TASK_ID, CREDIT_AMOUNT, address(0xDEAD));

        escrow.registerRevenue{value: revenue}(TASK_ID);

        uint256 lenderBefore   = lender.balance;
        uint256 borrowerBefore = borrower.balance;

        escrow.settle(TASK_ID);

        assertEq(lender.balance,   lenderBefore   + REPAY_AMOUNT,             "lender should receive repayAmount in KITE");
        assertEq(borrower.balance, borrowerBefore + (revenue - REPAY_AMOUNT), "borrower should receive remainder in KITE");

        (, , , , , , , KiteFuelEscrow.EscrowState state) = escrow.escrows(TASK_ID);
        assertEq(uint256(state), uint256(KiteFuelEscrow.EscrowState.Settled), "state must be Settled");
    }

    // Invariant: spend beyond creditAmount is always rejected
    function test_Revert_OverSpend() public {
        escrow.createTaskEscrow(TASK_ID, borrower, lender, CREDIT_AMOUNT, REPAY_AMOUNT);

        vm.prank(lender);
        escrow.fundCredit{value: CREDIT_AMOUNT}(TASK_ID);

        vm.prank(authorizedSigner);
        vm.expectRevert(KiteFuelEscrow.OverSpendLimit.selector);
        escrow.markSpend(TASK_ID, CREDIT_AMOUNT + 1, address(0xDEAD));
    }

    // Invariant: only the registered lender may fund the escrow
    function test_Revert_NonLenderFund() public {
        escrow.createTaskEscrow(TASK_ID, borrower, lender, CREDIT_AMOUNT, REPAY_AMOUNT);

        vm.prank(attacker);
        vm.expectRevert(KiteFuelEscrow.NotLender.selector);
        escrow.fundCredit{value: CREDIT_AMOUNT}(TASK_ID);
    }

    // Invariant: settle cannot be called unless the escrow is Active
    function test_Revert_SettleBeforeActive() public {
        escrow.createTaskEscrow(TASK_ID, borrower, lender, CREDIT_AMOUNT, REPAY_AMOUNT);

        vm.expectRevert(KiteFuelEscrow.InvalidState.selector);
        escrow.settle(TASK_ID);
    }

    // Invariant: cancel with zero spend/revenue refunds the lender in full (KITE returned)
    function test_CancelBeforeSpend() public {
        escrow.createTaskEscrow(TASK_ID, borrower, lender, CREDIT_AMOUNT, REPAY_AMOUNT);

        vm.prank(lender);
        escrow.fundCredit{value: CREDIT_AMOUNT}(TASK_ID);

        uint256 lenderBefore = lender.balance;

        escrow.cancelTask(TASK_ID);

        assertEq(lender.balance, lenderBefore + CREDIT_AMOUNT, "lender should be fully refunded in KITE");

        (, , , , , , , KiteFuelEscrow.EscrowState state) = escrow.escrows(TASK_ID);
        assertEq(uint256(state), uint256(KiteFuelEscrow.EscrowState.Cancelled), "state must be Cancelled");
    }

    // Invariant: when revenue (KITE) < repayAmount the lender receives all available revenue and borrower receives nothing
    function test_PartialRevenue() public {
        uint256 partialRevenue = 0.5 ether; // 0.5 KITE — below repayAmount of 1.1 KITE

        escrow.createTaskEscrow(TASK_ID, borrower, lender, CREDIT_AMOUNT, REPAY_AMOUNT);

        vm.prank(lender);
        escrow.fundCredit{value: CREDIT_AMOUNT}(TASK_ID);

        vm.prank(authorizedSigner);
        escrow.markSpend(TASK_ID, CREDIT_AMOUNT, address(0xDEAD));

        escrow.registerRevenue{value: partialRevenue}(TASK_ID);

        uint256 lenderBefore   = lender.balance;
        uint256 borrowerBefore = borrower.balance;

        escrow.settle(TASK_ID);

        assertEq(lender.balance,   lenderBefore + partialRevenue, "lender receives all available KITE revenue");
        assertEq(borrower.balance, borrowerBefore,                 "borrower receives nothing when KITE revenue < repayAmount");

        (, , , , , , , KiteFuelEscrow.EscrowState state) = escrow.escrows(TASK_ID);
        assertEq(uint256(state), uint256(KiteFuelEscrow.EscrowState.Settled), "state must be Settled");
    }
}
