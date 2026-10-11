import { useState, useEffect, useCallback } from 'react';
import type { TabId } from './components/Header';

export interface RouteConfig {
  id: TabId;
  path: string;
  aliases: string[];
  title: string;
}

export const ROUTES: RouteConfig[] = [
  {
    id: 'overview',
    path: '/dashboard',
    aliases: ['/', '/dashboard', '/overview'],
    title: 'Dashboard — FaceEngine',
  },
  {
    id: 'review',
    path: '/review',
    aliases: ['/review', '/review-queue'],
    title: 'Review Queue — FaceEngine',
  },
  {
    id: 'persons',
    path: '/household',
    aliases: ['/household', '/persons', '/members'],
    title: 'Household — FaceEngine',
  },
  {
    id: 'sandbox',
    path: '/sandbox',
    aliases: ['/sandbox', '/test'],
    title: 'Test Sandbox — FaceEngine',
  },
  {
    id: 'rtsp',
    path: '/rtsp',
    aliases: ['/rtsp', '/stream', '/mqtt'],
    title: 'RTSP & MQTT — FaceEngine',
  },
  {
    id: 'events',
    path: '/events',
    aliases: ['/events', '/logs', '/event-log'],
    title: 'Event Log — FaceEngine',
  },
  {
    id: 'settings',
    path: '/settings',
    aliases: ['/settings', '/config'],
    title: 'Settings — FaceEngine',
  },
  {
    id: 'account',
    path: '/account',
    aliases: ['/account', '/security', '/password', '/profile'],
    title: 'Account & Security — FaceEngine',
  },
  {
    id: 'guide',
    path: '/guide',
    aliases: ['/guide', '/integrations', '/docs'],
    title: 'Integrations — FaceEngine',
  },
];

/**
 * Resolves the active TabId from window.location.pathname or hash fallback.
 */
export function getTabFromPath(pathname: string, hash = ''): TabId {
  const cleanPath = (pathname || '/').replace(/\/+$/, '') || '/';

  // 1. Match by route aliases
  for (const route of ROUTES) {
    if (route.aliases.includes(cleanPath)) {
      return route.id;
    }
  }

  // 2. Check hash fallback (e.g. #/events or #events)
  if (hash) {
    const cleanHash = hash.replace(/^#\/?/, '/').replace(/\/+$/, '') || '/';
    for (const route of ROUTES) {
      if (route.aliases.includes(cleanHash)) {
        return route.id;
      }
    }
  }

  return 'overview';
}

/**
 * Returns canonical URL path for a given tab.
 */
export function getPathForTab(tabId: TabId): string {
  const route = ROUTES.find((r) => r.id === tabId);
  return route ? route.path : '/dashboard';
}

/**
 * Returns descriptive page title for a given tab.
 */
export function getTitleForTab(tabId: TabId): string {
  const route = ROUTES.find((r) => r.id === tabId);
  return route ? route.title : 'Household FaceEngine';
}

/**
 * Custom Hook for client-side HTML5 History API routing.
 * Synchronizes active tab state with browser URL bar and back/forward navigation.
 */
export function useAppRouter() {
  const [activeTab, setActiveTab] = useState<TabId>(() => {
    if (typeof window === 'undefined') return 'overview';
    return getTabFromPath(window.location.pathname, window.location.hash);
  });

  // Listen to browser Back and Forward navigation events (popstate)
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      const stateTab = event.state?.tab as TabId | undefined;
      const targetTab = stateTab || getTabFromPath(window.location.pathname, window.location.hash);
      setActiveTab(targetTab);
      document.title = getTitleForTab(targetTab);
    };

    window.addEventListener('popstate', handlePopState);

    // Initial title and state sync
    const initialTab = getTabFromPath(window.location.pathname, window.location.hash);
    document.title = getTitleForTab(initialTab);

    // Keep initial history entry synchronized
    if (!window.history.state || window.history.state.tab !== initialTab) {
      const currentPath = window.location.pathname === '/' ? '/' : getPathForTab(initialTab);
      window.history.replaceState({ tab: initialTab }, '', currentPath);
    }

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Programmatic navigation handler
  const navigateToTab = useCallback((targetTab: TabId, options?: { replace?: boolean }) => {
    setActiveTab((currentTab) => {
      const path = getPathForTab(targetTab);
      document.title = getTitleForTab(targetTab);

      if (options?.replace) {
        window.history.replaceState({ tab: targetTab }, '', path);
      } else if (currentTab !== targetTab || window.location.pathname !== path) {
        window.history.pushState({ tab: targetTab }, '', path);
      }

      return targetTab;
    });
  }, []);

  return {
    activeTab,
    navigateToTab,
    getPathForTab,
  };
}
