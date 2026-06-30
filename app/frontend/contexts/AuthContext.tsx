'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { recordLoginEvent } from '@/lib/api'
import { supabase } from '@/lib/supabaseClient'

interface AuthContextValue {
  user: User | null
  session: Session | null
  loading: boolean
  isPlatformAdmin: boolean
  signIn: (email: string, password: string) => Promise<{ error: string | null }>
  signUp: (email: string, password: string) => Promise<{ error: string | null }>
  signOut: () => Promise<void>
}

async function checkPlatformAdmin(userId: string): Promise<boolean> {
  const { data } = await supabase
    .from('platform_admins')
    .select('role')
    .eq('user_id', userId)
    .eq('status', 'active')
    .limit(1)
  return (data?.length ?? 0) > 0
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  session: null,
  loading: true,
  isPlatformAdmin: false,
  signIn: async () => ({ error: 'Not initialized' }),
  signUp: async () => ({ error: 'Not initialized' }),
  signOut: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data }) => {
      setSession(data.session)
      if (data.session?.user) {
        setIsPlatformAdmin(await checkPlatformAdmin(data.session.user.id))
      }
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange(async (event, newSession) => {
      setSession(newSession)
      if (newSession?.user) {
        setIsPlatformAdmin(await checkPlatformAdmin(newSession.user.id))
      } else {
        setIsPlatformAdmin(false)
      }
      setLoading(false)
      if (event === 'SIGNED_IN' && newSession) {
        recordLoginEvent().catch(() => {})
      }
    })

    return () => {
      listener.subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    return { error: error?.message ?? null }
  }

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password })
    return { error: error?.message ?? null }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  return (
    <AuthContext.Provider
      value={{ user: session?.user ?? null, session, loading, isPlatformAdmin, signIn, signUp, signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}
