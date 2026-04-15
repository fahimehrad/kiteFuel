// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Deployed on Kite Chain Testnet — https://testnet.kitescan.ai
// Native token: KITE. All value amounts (creditAmount, repayAmount, revenue) are in wei (KITE).

contract KiteFuelEscrow {
    // -------------------------------------------------------------------------
    // Enums
    // -------------------------------------------------------------------------

    enum EscrowState {
        Created,
        Funded,
        Active,
        Settled,
        Cancelled
    }

    // -------------------------------------------------------------------------
    // Structs
    // -------------------------------------------------------------------------

    struct TaskEscrow {
        bytes32 taskId;
        address borrower;
        address lender;
        uint256 creditAmount;
        uint256 repayAmount;
        uint256 spentAmount;
        uint256 revenue;
        EscrowState state;
    }

    // -------------------------------------------------------------------------
    // State Variables
    // -------------------------------------------------------------------------

    address public immutable authorizedSigner;

    mapping(bytes32 => TaskEscrow) public escrows;
    mapping(bytes32 => bool) public exists;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    event EscrowCreated(bytes32 taskId, address borrower, address lender, uint256 creditAmount);
    event CreditFunded(bytes32 taskId, uint256 amount);
    event SpendRecorded(bytes32 taskId, uint256 amount, address provider);
    event RevenueRegistered(bytes32 taskId, uint256 amount);
    event LenderRepaid(bytes32 taskId, uint256 amount);
    event RemainderReleased(bytes32 taskId, uint256 amount);

    // -------------------------------------------------------------------------
    // Custom Errors
    // -------------------------------------------------------------------------

    error NotLender();
    error NotAuthorized();
    error InsufficientFunds();
    error RepayFirst();
    error OverSpendLimit();
    error InvalidState();
    error TaskAlreadyExists();
    error TaskNotFound();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    constructor(address _authorizedSigner) {
        authorizedSigner = _authorizedSigner;
    }

    // -------------------------------------------------------------------------
    // Functions
    // -------------------------------------------------------------------------

    function createTaskEscrow(
        bytes32 taskId,
        address borrower,
        address lender,
        uint256 creditAmount,
        uint256 repayAmount
    ) external {
        if (exists[taskId]) revert TaskAlreadyExists();

        escrows[taskId] = TaskEscrow({
            taskId: taskId,
            borrower: borrower,
            lender: lender,
            creditAmount: creditAmount,
            repayAmount: repayAmount,
            spentAmount: 0,
            revenue: 0,
            state: EscrowState.Created
        });

        exists[taskId] = true;

        emit EscrowCreated(taskId, borrower, lender, creditAmount);
    }

    /// @notice Lender funds the escrow with exactly creditAmount KITE.
    function fundCredit(bytes32 taskId) external payable {
        if (!exists[taskId]) revert TaskNotFound();

        TaskEscrow storage escrow = escrows[taskId];

        if (msg.sender != escrow.lender) revert NotLender();
        if (escrow.state != EscrowState.Created) revert InvalidState();
        if (msg.value != escrow.creditAmount) revert InsufficientFunds();

        escrow.state = EscrowState.Funded;
        escrow.state = EscrowState.Active;

        emit CreditFunded(taskId, msg.value);
    }

    function markSpend(bytes32 taskId, uint256 amount, address provider) external {
        if (!exists[taskId]) revert TaskNotFound();

        TaskEscrow storage escrow = escrows[taskId];

        if (msg.sender != authorizedSigner) revert NotAuthorized();
        if (escrow.state != EscrowState.Active) revert InvalidState();
        if (escrow.spentAmount + amount > escrow.creditAmount) revert OverSpendLimit();

        escrow.spentAmount += amount;

        emit SpendRecorded(taskId, amount, provider);
    }

    /// @notice User sends revenue (in KITE) into the escrow to be settled.
    function registerRevenue(bytes32 taskId) external payable {
        if (!exists[taskId]) revert TaskNotFound();

        TaskEscrow storage escrow = escrows[taskId];

        if (escrow.state != EscrowState.Active) revert InvalidState();

        escrow.revenue += msg.value;

        emit RevenueRegistered(taskId, msg.value);
    }

    /// @notice Settles the escrow: pays the lender first (up to repayAmount KITE),
    ///         then releases any remaining KITE to the borrower.
    function settle(bytes32 taskId) external {
        if (!exists[taskId]) revert TaskNotFound();

        TaskEscrow storage escrow = escrows[taskId];

        if (escrow.state != EscrowState.Active) revert InvalidState();

        uint256 lenderPayment = escrow.revenue >= escrow.repayAmount
            ? escrow.repayAmount
            : escrow.revenue;

        payable(escrow.lender).transfer(lenderPayment);
        emit LenderRepaid(taskId, lenderPayment);

        if (escrow.revenue > escrow.repayAmount) {
            uint256 remainder = escrow.revenue - escrow.repayAmount;
            payable(escrow.borrower).transfer(remainder);
            emit RemainderReleased(taskId, remainder);
        }

        escrow.state = EscrowState.Settled;
    }

    function cancelTask(bytes32 taskId) external {
        if (!exists[taskId]) revert TaskNotFound();

        TaskEscrow storage escrow = escrows[taskId];

        if (escrow.state == EscrowState.Created) {
            escrow.state = EscrowState.Cancelled;
        } else if (escrow.state == EscrowState.Funded || escrow.state == EscrowState.Active) {
            if (escrow.spentAmount != 0 || escrow.revenue != 0) revert InvalidState();
            payable(escrow.lender).transfer(escrow.creditAmount);
            escrow.state = EscrowState.Cancelled;
        } else {
            revert InvalidState();
        }
    }
}
