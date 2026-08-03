import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { User, Mail, Bell, Save } from 'lucide-react'
import { authApi } from '../api/auth'
import useAuthStore from '../store/authStore'
import Card, { CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const [profile, setProfile] = useState({
    display_name: '',
    email: '',
    smtp_host: '',
    smtp_port: '',
    smtp_user: '',
    smtp_pass: '',
    slack_webhook: '',
  })
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (user) {
      setProfile(p => ({
        ...p,
        display_name: user.display_name || '',
        email: user.email || '',
        smtp_host: user.smtp_host || '',
        smtp_port: user.smtp_port || '',
        smtp_user: user.smtp_user || '',
        slack_webhook: user.slack_webhook || '',
      }))
    }
  }, [user])

  const saveMutation = useMutation({
    mutationFn: () => authApi.updateProfile(profile).then(r => r.data),
    onSuccess: (data) => {
      setUser(data)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const field = (key) => ({
    value: profile[key] || '',
    onChange: (e) => setProfile(p => ({ ...p, [key]: e.target.value })),
  })

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Profile Settings</h1>
        <p className="text-slate-400 text-sm mt-0.5">Manage your account and notification preferences</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="w-4 h-4 text-brand" /> Account
          </CardTitle>
        </CardHeader>
        <div className="space-y-4">
          <Input label="Display Name" placeholder="Your name" {...field('display_name')} />
          <Input label="Email" type="email" disabled value={profile.email} className="opacity-60" />
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-brand" /> Email / SMTP
          </CardTitle>
        </CardHeader>
        <div className="grid grid-cols-2 gap-4">
          <Input label="SMTP Host" placeholder="smtp.gmail.com" {...field('smtp_host')} />
          <Input label="SMTP Port" type="number" placeholder="587" {...field('smtp_port')} />
          <Input label="SMTP Username" placeholder="user@gmail.com" {...field('smtp_user')} />
          <Input label="SMTP Password" type="password" placeholder="••••••••" {...field('smtp_pass')} />
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-brand" /> Notifications
          </CardTitle>
        </CardHeader>
        <Input
          label="Slack Webhook URL"
          placeholder="https://hooks.slack.com/services/..."
          {...field('slack_webhook')}
        />
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
          <Save className="w-4 h-4" /> Save Changes
        </Button>
        {saved && <span className="text-sm text-emerald-400">✓ Saved successfully</span>}
        {saveMutation.error && (
          <span className="text-sm text-red-400">
            {saveMutation.error.response?.data?.detail || 'Save failed'}
          </span>
        )}
      </div>
    </div>
  )
}
