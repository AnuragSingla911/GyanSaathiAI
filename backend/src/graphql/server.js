const { ApolloServer } = require('apollo-server-express');
const typeDefs = require('./schema');
const resolvers = require('./resolvers');

// Custom scalar resolvers
const scalarResolvers = {
  DateTime: {
    serialize: (value) => value.toISOString(),
    parseValue: (value) => new Date(value),
    parseLiteral: (ast) => new Date(ast.value)
  },
  JSON: {
    serialize: (value) => value,
    parseValue: (value) => value,
    parseLiteral: (ast) => ast.value
  }
};

// Context function to extract user from JWT token
const context = async ({ req }) => {
  // Get the user token from the headers
  const token = req.headers.authorization?.replace('Bearer ', '');
  
  if (!token) {
    console.log('GraphQL Context: No token provided');
    return { user: null };
  }
  
  try {
    // Verify the token
    const jwt = require('jsonwebtoken');
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'fallback-secret');
    
    console.log('GraphQL Context: Token decoded successfully:', decoded);
    
    // Return the user info
    return { user: decoded };
  } catch (error) {
    console.error('GraphQL Context: Token verification failed:', error.message);
    return { user: null };
  }
};

// Create Apollo Server
const createApolloServer = () => {
  return new ApolloServer({
    typeDefs,
    resolvers: {
      ...resolvers,
      ...scalarResolvers
    },
    context,
    introspection: process.env.NODE_ENV !== 'production',
    playground: process.env.NODE_ENV !== 'production',
    formatError: (error) => {
      // Log errors for debugging
      console.error('GraphQL Error:', error);
      
      // Return user-friendly error messages
      return {
        message: error.message,
        code: error.extensions?.code || 'INTERNAL_SERVER_ERROR',
        path: error.path
      };
    },
    plugins: [
      // Add request logging
      {
        requestDidStart: async (requestContext) => {
          const start = Date.now();
          
          return {
            willSendResponse: async (requestContext) => {
              const duration = Date.now() - start;
              console.log(`GraphQL ${requestContext.operation?.operation || 'query'} completed in ${duration}ms`);
            }
          };
        }
      }
    ]
  });
};

module.exports = { createApolloServer };
