Frontend
========

The YAAAF frontend is a modern Next.js application that provides a real-time chat interface for interacting with the agent system.

Architecture Overview
---------------------

Technology Stack
~~~~~~~~~~~~~~~

* **Next.js 14**: React framework with App Router
* **TypeScript**: Type-safe development
* **Tailwind CSS**: Utility-first styling
* **shadcn/ui**: Component library
* **pnpm**: Package management

Project Structure
~~~~~~~~~~~~~~~~

.. code-block:: text

   frontend/
   ├── apps/
   │   └── www/                    # Main application
   │       ├── app/               # Next.js App Router
   │       ├── components/        # React components
   │       ├── lib/              # Utilities
   │       └── public/           # Static assets
   ├── registry/                  # Component registry
   └── packages/                  # Shared packages

Key Components
--------------

Chat Interface
~~~~~~~~~~~~~

**Location**: ``apps/www/registry/default/ui/chat.tsx``

The main chat interface component handles:

* Real-time message streaming
* Agent response formatting
* Artifact display
* User input handling

**Features**:
   * Markdown rendering for rich text
   * Code syntax highlighting
   * Inline artifact display
   * Responsive design

**Usage**:

.. code-block:: tsx

   import { Chat } from "@/registry/default/ui/chat"
   
   export default function ChatPage() {
     return <Chat />
   }

Message Components
~~~~~~~~~~~~~~~~~

**Message Container**: ``chat-message.tsx``

Handles individual message display with:

* Agent identification
* Timestamp formatting
* Content rendering
* Artifact embedding

**Message Types**:

.. code-block:: typescript

   interface Message {
     content: string
     role: 'user' | 'assistant' | 'system'
     timestamp?: Date
     agent?: string
   }

API Integration
--------------

Chat API Route
~~~~~~~~~~~~~

**Location**: ``apps/www/app/api/chat/route.ts``

Handles communication with the YAAAF backend:

* Stream creation
* Real-time message polling
* Note formatting
* Error handling

**Data Flow**:

1. **User Input**: Chat component captures user message
2. **Stream Creation**: API creates new conversation stream
3. **Polling**: Frontend polls for new messages/notes
4. **Formatting**: Notes are converted to display format
5. **Rendering**: Messages are displayed with agent attribution

Note Processing
~~~~~~~~~~~~~~

The frontend converts backend ``Note`` objects into user-friendly format:

.. code-block:: typescript

   interface Note {
     message: string
     artefact_id: string | null
     agent_name: string | null
   }

   function formatNoteToString(note: Note): string {
     let result = ""
     
     // Wrap message in agent name tags if agent name exists
     if (note.agent_name) {
       result = `<${note.agent_name}>${note.message}</${note.agent_name}>`
     } else {
       result = note.message
     }
     
     // Add artefact information if artefact_id exists
     if (note.artefact_id) {
       result += `\n<Artefact>${note.artefact_id}</Artefact>`
     }
     
     return result
   }

Settings Configuration
~~~~~~~~~~~~~~~~~~~~~

**Location**: ``apps/www/app/settings.ts``

Configures backend endpoints:

.. code-block:: typescript

   export const port = process.env.NEXT_PUBLIC_BACKEND_PORT || "4000"
   export const create_stream_url = `http://localhost:${port}/create_stream`
   export const get_utterances_url = `http://localhost:${port}/get_utterances`
   export const complete_tag = "<task-completed/>"

Component Registry
-----------------

YAAAF uses a component registry system for managing UI components:

Registry Structure
~~~~~~~~~~~~~~~~~

.. code-block:: text

   registry/
   ├── default/
   │   └── ui/
   │       ├── chat.tsx           # Main chat component
   │       ├── chat-message.tsx   # Message display
   │       ├── button.tsx         # Button component
   │       └── input.tsx          # Input component
   └── schema.ts                  # Registry schema

Building the Registry
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   cd frontend
   pnpm build:registry

This compiles the component registry for use in the application.

Styling
-------

Tailwind CSS
~~~~~~~~~~~

The frontend uses Tailwind CSS for styling:

**Configuration**: ``tailwind.config.js``

.. code-block:: javascript

   module.exports = {
     content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
     theme: {
       extend: {
         colors: {
           border: "hsl(var(--border))",
           background: "hsl(var(--background))",
           // ... theme colors
         }
       }
     }
   }

shadcn/ui Integration
~~~~~~~~~~~~~~~~~~~

Components follow the shadcn/ui design system:

* Consistent design tokens
* Accessible components
* Dark/light mode support
* Customizable themes

Development
-----------

Local Development
~~~~~~~~~~~~~~~~

.. code-block:: bash

   cd frontend
   pnpm install
   pnpm dev

This starts the development server on ``http://localhost:3000``.

TypeScript Configuration
~~~~~~~~~~~~~~~~~~~~~~~

**tsconfig.json**:

.. code-block:: json

   {
     "compilerOptions": {
       "target": "es5",
       "lib": ["dom", "dom.iterable", "esnext"],
       "allowJs": true,
       "skipLibCheck": true,
       "strict": true,
       "forceConsistentCasingInFileNames": true,
       "noEmit": true,
       "esModuleInterop": true,
       "module": "esnext",
       "moduleResolution": "node",
       "resolveJsonModule": true,
       "isolatedModules": true,
       "jsx": "preserve",
       "incremental": true,
       "plugins": [
         {
           "name": "next"
         }
       ],
       "baseUrl": ".",
       "paths": {
         "@/*": ["./app/*"],
         "@/registry/*": ["./registry/*"]
       }
     }
   }

Code Quality
~~~~~~~~~~~

**ESLint Configuration**:

.. code-block:: bash

   pnpm lint        # Run linting
   pnpm lint:fix    # Fix linting issues

**Prettier Formatting**:

.. code-block:: bash

   pnpm format:check    # Check formatting
   pnpm format:write    # Apply formatting

**Type Checking**:

.. code-block:: bash

   pnpm typecheck      # Run TypeScript checks

Building and Deployment
-----------------------

Production Build
~~~~~~~~~~~~~~~

.. code-block:: bash

   cd frontend
   pnpm build

This creates an optimized production build in the ``.next`` directory.

Environment Variables
~~~~~~~~~~~~~~~~~~~~

**Development**: ``.env.local``

.. code-block:: env

   NEXT_PUBLIC_BACKEND_PORT=4000
   NEXT_PUBLIC_API_URL=http://localhost:4000

**Production**: Configure environment variables in deployment platform

Deployment Options
~~~~~~~~~~~~~~~~~

**Vercel** (Recommended):

.. code-block:: bash

   pnpm dlx vercel

**Docker**:

.. code-block:: dockerfile

   FROM node:18-alpine
   WORKDIR /app
   COPY package*.json ./
   RUN npm ci --only=production
   COPY . .
   RUN npm run build
   EXPOSE 3000
   CMD ["npm", "start"]

**Static Export**:

.. code-block:: bash

   pnpm build && pnpm export

Customization
------------

Adding New Components
~~~~~~~~~~~~~~~~~~~~

1. **Create Component**:

   .. code-block:: tsx

      // components/custom-component.tsx
      export function CustomComponent() {
        return <div>Custom Content</div>
      }

2. **Register Component**:

   .. code-block:: typescript

      // registry/default/ui/custom-component.tsx
      export { CustomComponent } from "@/components/custom-component"

3. **Use in Application**:

   .. code-block:: tsx

      import { CustomComponent } from "@/registry/default/ui/custom-component"

Extending the Chat Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To add new features to the chat interface:

1. **Modify Chat Component**: Add new props and state
2. **Update API Route**: Handle new data types
3. **Add Styling**: Extend Tailwind classes
4. **Update Types**: Add TypeScript interfaces

Theme Customization
~~~~~~~~~~~~~~~~~~

Modify the theme in ``app/globals.css``:

.. code-block:: css

   :root {
     --background: 0 0% 100%;
     --foreground: 222.2 84% 4.9%;
     --primary: 222.2 47.4% 11.2%;
     /* ... custom variables */
   }

Error Handling
--------------

Frontend Error Handling
~~~~~~~~~~~~~~~~~~~~~~

The frontend implements comprehensive error handling:

**API Errors**:

.. code-block:: typescript

   try {
     const response = await fetch(url, options)
     if (!response.ok) {
       throw new Error(`HTTP ${response.status}: ${response.statusText}`)
     }
     return await response.json()
   } catch (error) {
     console.error('API Error:', error)
     // Handle error appropriately
   }

**React Error Boundaries**:

.. code-block:: tsx

   class ErrorBoundary extends React.Component {
     constructor(props) {
       super(props)
       this.state = { hasError: false }
     }
     
     static getDerivedStateFromError(error) {
       return { hasError: true }
     }
     
     render() {
       if (this.state.hasError) {
         return <div>Something went wrong.</div>
       }
       return this.props.children
     }
   }

Performance Optimization
-----------------------

Code Splitting
~~~~~~~~~~~~~

Next.js automatically splits code for optimal loading:

.. code-block:: tsx

   import dynamic from 'next/dynamic'
   
   const DynamicComponent = dynamic(() => import('./heavy-component'), {
     loading: () => <p>Loading...</p>,
   })

Image Optimization
~~~~~~~~~~~~~~~~~

Use Next.js Image component for optimized images:

.. code-block:: tsx

   import Image from 'next/image'
   
   <Image
     src="/image.jpg"
     alt="Description"
     width={500}
     height={300}
     priority
   />

Caching
~~~~~~

Implement appropriate caching strategies:

.. code-block:: typescript

   // API route caching
   export const revalidate = 3600 // 1 hour
   
   // Client-side caching
   const cache = new Map()
   function getCachedData(key: string) {
     return cache.get(key)
   }