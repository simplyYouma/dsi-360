import { api } from '@/lib/api';

export const authApi = {
  motDePasseOublie: (email: string): Promise<void> =>
    api.post('/auth/mot-de-passe-oublie', { email }),
  reinitialiser: (jeton: string, nouveau: string): Promise<void> =>
    api.post('/auth/reinitialiser', { jeton, nouveau }),
};
