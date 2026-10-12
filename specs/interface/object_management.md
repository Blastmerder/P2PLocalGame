# Business Logic: Object Data Management

## Description
Handles the lifecycle and state updates of objects within the application.

## Logic Details
- **Object Initialization**: When a new object name is provided via the terminal input and confirmed with 'Enter', the `ObjectAPI.init_object` method is called to create a new object with default properties: `{'name': <name>, 'status': 'Active', 'value': 0}`.
- **Periodic Data Update**: Every 1.0 seconds, the system iterates through all existing objects and updates their state using `ObjectAPI.get_update`, which increments the `value` field.

## Input/Output
- **Inputs**: 
  - String (name) for creation.
  - Timer (1s interval) for updates.
- **Outputs**: 
  - Updated object dictionary in the `objects` list.
