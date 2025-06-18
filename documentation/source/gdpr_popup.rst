GDPR Disclaimer Popup
======================

This document describes the GDPR disclaimer popup feature that appears when users first access the YAAAF web interface.

Overview
--------

The GDPR disclaimer popup is a privacy notice that:

* Appears once per browser when a user first visits the application
* Explains how user data is processed
* Complies with GDPR requirements for user consent
* Can be enabled/disabled via environment variable

Configuration
-------------

Environment Variable
^^^^^^^^^^^^^^^^^^^^^

The popup can be controlled using the ``YAAAF_ACTIVATE_POPUP`` environment variable:

.. code-block:: bash

   # Enable the popup (default behavior)
   export YAAAF_ACTIVATE_POPUP=true

   # Disable the popup
   export YAAAF_ACTIVATE_POPUP=false

Usage Examples
^^^^^^^^^^^^^^

To disable the popup:

.. code-block:: bash

   # Set environment variable and start the application
   export YAAAF_ACTIVATE_POPUP=false
   python -m yaaaf frontend 3000

To enable the popup (default):

.. code-block:: bash

   # Either don't set the variable, or explicitly enable it
   export YAAAF_ACTIVATE_POPUP=true
   python -m yaaaf frontend 3000

   # Or simply start without setting the variable (defaults to enabled)
   python -m yaaaf frontend 3000

Technical Implementation
------------------------

Frontend Component
^^^^^^^^^^^^^^^^^^

The GDPR disclaimer is implemented as a React component (``components/gdpr-disclaimer.tsx``) that:

1. **Checks environment variable**: Reads ``NEXT_PUBLIC_YAAAF_ACTIVATE_POPUP`` from Next.js environment
2. **Tracks user acceptance**: Uses localStorage to remember if user has already accepted
3. **Shows modal overlay**: Displays a centered modal with backdrop when needed
4. **Handles acceptance**: Stores acceptance in localStorage and hides the popup

Key Features
^^^^^^^^^^^^

* **One-time display**: Only shows once per browser session
* **Smooth animations**: Fade-in/fade-out transitions
* **Responsive design**: Works on desktop and mobile
* **Accessible**: Keyboard navigation and ARIA compliance
* **Environment-driven**: Can be disabled for internal deployments

Persistence
^^^^^^^^^^^

User acceptance is stored in the browser's localStorage with the key ``gdpr-disclaimer-accepted``. This ensures the popup only appears once per browser, even across multiple sessions.

Privacy Notice Content
-----------------------

The popup displays a GDPR-compliant privacy notice that:

* Explains that conversations are processed to provide AI responses
* Mentions GDPR compliance
* States that no personal data is stored permanently
* Informs users of their right to request data deletion
* Requires explicit user consent to proceed

Files Modified
--------------

**Frontend:**

* ``frontend/apps/www/components/gdpr-disclaimer.tsx`` - Main component
* ``frontend/apps/www/app/layout.tsx`` - Integration into app layout
* ``frontend/apps/www/next.config.mjs`` - Environment variable configuration
* ``frontend/.env.example`` - Example environment configuration

**Backend:**

* ``yaaaf/client/run.py`` - Pass-through environment variable to frontend

Compliance Notes
----------------

This implementation helps with GDPR compliance by:

* ✅ **Providing clear information** about data processing
* ✅ **Obtaining explicit consent** before processing begins
* ✅ **Allowing users to understand** their rights
* ✅ **Being easily configurable** for different deployment contexts

For full GDPR compliance, organizations should also ensure:

* Proper data handling procedures are in place
* Privacy policies are accessible and comprehensive
* Data subject rights (access, deletion, portability) are implemented
* Data processing activities are documented

Customization
-------------

To customize the popup content, edit the JSX in ``components/gdpr-disclaimer.tsx``. The component is designed to be easily modifiable while maintaining accessibility and responsive design.