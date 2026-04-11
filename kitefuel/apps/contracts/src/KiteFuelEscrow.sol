// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

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
    ) external {}

    function fundCredit(bytes32 taskId) external payable {}

    function markSpend(bytes32 taskId, uint256 amount, address provider) external {}

    function registerRevenue(bytes32 taskId) external payable {}

    function settle(bytes32 taskId) external {}

    function cancelTask(bytes32 taskId) external {}
}
