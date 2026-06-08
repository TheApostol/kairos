'use client'

import * as React from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const AlertDialog = Dialog
const AlertDialogTrigger = DialogTrigger

const AlertDialogContent = React.forwardRef<
  React.ElementRef<typeof DialogContent>,
  React.ComponentPropsWithoutRef<typeof DialogContent>
>(({ className, ...props }, ref) => (
  <DialogContent ref={ref} className={cn('max-w-md', className)} {...props} />
))
AlertDialogContent.displayName = 'AlertDialogContent'

const AlertDialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <DialogHeader className={cn('text-left', className)} {...props} />
)
AlertDialogHeader.displayName = 'AlertDialogHeader'

const AlertDialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <DialogFooter className={cn('flex-row justify-end gap-2', className)} {...props} />
)
AlertDialogFooter.displayName = 'AlertDialogFooter'

const AlertDialogTitle = DialogTitle
const AlertDialogDescription = DialogDescription

interface AlertDialogActionProps extends React.ComponentPropsWithoutRef<typeof Button> {
  onClick?: React.MouseEventHandler<HTMLButtonElement>
}

const AlertDialogAction = React.forwardRef<HTMLButtonElement, AlertDialogActionProps>(
  ({ children, onClick, ...props }, ref) => (
    <DialogClose asChild>
      <Button ref={ref} onClick={onClick} {...props}>
        {children}
      </Button>
    </DialogClose>
  )
)
AlertDialogAction.displayName = 'AlertDialogAction'

const AlertDialogCancel = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<typeof Button>
>(({ children, ...props }, ref) => (
  <DialogClose asChild>
    <Button ref={ref} variant="outline" {...props}>
      {children}
    </Button>
  </DialogClose>
))
AlertDialogCancel.displayName = 'AlertDialogCancel'

export {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
}
