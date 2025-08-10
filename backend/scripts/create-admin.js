const bcrypt = require('bcrypt');
const { Pool } = require('pg');

const createAdminUser = async () => {
  const pool = new Pool({
    host: process.env.DB_HOST || 'localhost',
    port: process.env.DB_PORT || 5432,
    database: process.env.DB_NAME || 'tutor_db',
    user: process.env.DB_USER || 'tutor_user',
    password: process.env.DB_PASSWORD || 'tutor_password',
  });

  try {
    console.log('🔄 Creating admin user...');
    
    // Hash the password
    const hashedPassword = await bcrypt.hash('admin123', 10);
    
    // Insert admin user
    const insertQuery = `
      INSERT INTO users (username, email, password_hash, role)
      VALUES ($1, $2, $3, $4)
      ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        role = EXCLUDED.role
      RETURNING user_id, username, email, role;
    `;
    
    const result = await pool.query(insertQuery, [
      'admin',
      'admin@tutor.app',
      hashedPassword,
      'admin'
    ]);
    
    console.log('✅ Admin user created/updated:', result.rows[0]);
    
    await pool.end();
    process.exit(0);
  } catch (error) {
    console.error('❌ Error creating admin user:', error.message);
    process.exit(1);
  }
};

createAdminUser();
