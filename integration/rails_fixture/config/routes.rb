Rails.application.routes.draw do
  root 'events#index'
  resources :events, param: :slug, only: [:index, :show, :new, :create]
  namespace :admin do
    resources :events, only: :index
  end
  scope '(:locale)' do
    resources :talks, param: :slug, only: :show
  end
  get '/venues/:slug', to: 'venues#show', as: :venue
  get '/venues/new', to: 'venues#new', as: :new_venue
  mount Embedded::Engine => '/embedded'
end
