import Git from '@/components/settings/Git.vue'
import Workers from '@/components/settings/Workers.vue'
import S3Bucket from '@/components/settings/S3Bucket.vue'
import LLM from '@/components/settings/LLM.vue'
import Firewall from '@/components/settings/Firewall.vue'
import Waf from '@/components/settings/Waf.vue'
import SshKeys from '@/components/settings/SshKeys.vue'

// Single source of truth for id/label/component so SettingsDialog can resolve
// a routed subsection id without each page owning its own private mapping.
export const GENERAL_SECTIONS = [
  {
    id: 'github',
    label: 'Git settings',
    description: 'Connect GitHub for private installs and repo browsing.',
    component: Git,
  },
  {
    id: 's3-bucket',
    label: 'Object storage settings',
    description: 'Connect S3-compatible storage for offsite backups.',
    component: S3Bucket,
  },
  {
    id: 'llm',
    label: 'AI assistant settings',
    description: 'Connect an LLM provider to power assistant features.',
    component: LLM,
  },
  {
    id: 'workers',
    label: 'Background workers',
    description: 'Configure background worker groups and queues.',
    component: Workers,
  },
]

export const SECURITY_SECTIONS = [
  {
    id: 'firewall',
    label: 'Firewall settings',
    description: 'Restrict server access with IP allow and block rules.',
    component: Firewall,
  },
  {
    id: 'waf',
    label: 'WAF settings',
    description: 'Web application firewall rules for your sites.',
    component: Waf,
  },
  {
    id: 'ssh-keys',
    label: 'SSH keys',
    description: 'Manage authorized public keys for server access.',
    component: SshKeys,
  },
]
