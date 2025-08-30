import { ApolloClient, InMemoryCache, createHttpLink, from } from '@apollo/client';
import { setContext } from '@apollo/client/link/context';
import { onError } from '@apollo/client/link/error';

// HTTP link for GraphQL endpoint
const httpLink = createHttpLink({
  uri: import.meta.env.VITE_GRAPHQL_URL || 'http://localhost:5000/graphql',
});

// Auth link to add JWT token to requests
const authLink = setContext((_, { headers }) => {
  const token = localStorage.getItem('token');
  return {
    headers: {
      ...headers,
      authorization: token ? `Bearer ${token}` : '',
    },
  };
});

// Error handling link
const errorLink = onError(({ graphQLErrors, networkError }) => {
  if (graphQLErrors) {
    graphQLErrors.forEach(({ message, locations, path, extensions }) => {
      console.error(
        `[GraphQL error]: Message: ${message}, Location: ${locations}, Path: ${path}`
      );
      
      // Handle authentication errors
      if (extensions?.code === 'UNAUTHENTICATED') {
        localStorage.removeItem('token');
        window.location.href = '/login';
        return;
      }
    });
  }

  if (networkError) {
    console.error(`[Network error]: ${networkError}`);
    
    if ((networkError as any).statusCode === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      return;
    }
  }
});

// Cache configuration
const cache = new InMemoryCache({
  typePolicies: {
    Query: {
      fields: {
        questions: {
          keyArgs: ['subject', 'topic', 'difficulty', 'status'],
          merge: (_, incoming) => incoming,
        },
        userProgress: {
          keyArgs: ['userId', 'scope'],
          merge: (_, incoming) => incoming,
        },
        progress: {
          keyArgs: ['userId'],
          merge: (_, incoming) => incoming,
        },
        analytics: {
          keyArgs: ['userId', 'timeframe'],
          merge: (_, incoming) => incoming,
        },
      },
    },
    QuizAttempt: {
      fields: {
        items: {
          merge: (_, incoming) => incoming,
        },
      },
    },
  },
});

// Create Apollo Client
export const client = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache,
  defaultOptions: {
    watchQuery: {
      errorPolicy: 'all',
    },
    query: {
      errorPolicy: 'all',
    },
  },
});

export default client;
